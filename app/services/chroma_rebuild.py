from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import isfinite
from pathlib import Path
from typing import BinaryIO

from app.schemas import PaperParseResult
from app.services.chunker import chunk_paper
from app.services.vector_backends.base import validate_embeddings

HASH_BLOCK_SIZE = 1024 * 1024
PROTECTED_CONTRACT_FIELDS = (
    "collection",
    "provider",
    "model",
    "git_head",
    "schema_version",
    "chunk_settings",
)
_MANIFEST_LOCK_TIMEOUT_SECONDS = 10.0
_LOCAL_MANIFEST_LOCKS: dict[str, threading.RLock] = {}
_LOCAL_MANIFEST_LOCKS_GUARD = threading.Lock()


def discover_parsed_sources(metadata_dir: Path) -> list[Path]:
    """Return top-level parsed-paper JSON files in deterministic filename order."""
    metadata_root = metadata_dir.resolve()
    sources: list[Path] = []
    for candidate in metadata_dir.glob("*_parsed.json"):
        try:
            candidate.resolve().relative_to(metadata_root)
        except ValueError as exc:
            raise ValueError(
                f"parsed source resolves outside metadata directory: {candidate.name}"
            ) from exc
        if candidate.is_file():
            sources.append(candidate)
    return sorted(sources, key=lambda path: path.name)


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(HASH_BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict | None:
    """Load a manifest object, returning None only when the path is absent."""
    if not path.exists():
        return None
    manifest = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_non_finite_json_constant,
    )
    if not isinstance(manifest, dict):
        raise ValueError("manifest must contain a top-level JSON object")
    return manifest


def _reject_non_finite_json_constant(constant: str) -> None:
    raise ValueError(f"manifest contains non-finite JSON constant: {constant}")


def _is_windows_sharing_violation(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) and getattr(exc, "winerror", None) in {
        32,
        33,
    }


def write_manifest(
    path: Path,
    manifest: dict,
    *,
    replace_attempts: int = 3,
    replace_delay: float = 0.05,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Atomically replace a UTF-8 JSON manifest after flushing it to disk."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must contain a top-level JSON object")
    _positive_int(replace_attempts, "replace_attempts")
    _nonnegative_finite(replace_delay, "replace_delay")
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(1, replace_attempts + 1):
            try:
                os.replace(temporary, path)
                break
            except OSError as exc:
                if (
                    not _is_windows_sharing_violation(exc)
                    or attempt == replace_attempts
                ):
                    raise
                sleep(replace_delay * attempt)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            # Preserve the original write failure if the explicit temp cannot be cleaned.
            pass


def _manifest_local_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCAL_MANIFEST_LOCKS_GUARD:
        return _LOCAL_MANIFEST_LOCKS.setdefault(key, threading.RLock())


def _try_file_lock(handle: BinaryIO) -> bool:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _release_file_lock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def manifest_write_lock(
    path: Path, *, timeout: float = _MANIFEST_LOCK_TIMEOUT_SECONDS
) -> Iterator[None]:
    """Serialize manifest read-modify-write sequences across threads/processes."""
    _nonnegative_finite(timeout, "lock timeout")
    path.parent.mkdir(parents=True, exist_ok=True)
    local_lock = _manifest_local_lock(path)
    if not local_lock.acquire(timeout=timeout):
        raise TimeoutError(f"Timed out locking rebuild manifest {path.name!r}")
    lock_path = path.with_name(f".{path.name}.lock")
    handle: BinaryIO | None = None
    file_locked = False
    try:
        handle = open(lock_path, "a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while not _try_file_lock(handle):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out locking rebuild manifest {path.name!r}")
            time.sleep(0.01)
        file_locked = True
        yield
    finally:
        try:
            if handle is not None:
                try:
                    if file_locked:
                        _release_file_lock(handle)
                finally:
                    handle.close()
        finally:
            local_lock.release()


def update_manifest_locked(
    path: Path,
    updater: Callable[[dict], dict],
    *,
    timeout: float = _MANIFEST_LOCK_TIMEOUT_SECONDS,
) -> dict:
    """Apply one process-safe manifest read-modify-write transaction."""
    with manifest_write_lock(path, timeout=timeout):
        existing = load_manifest(path)
        if existing is None:
            raise FileNotFoundError(path)
        updated = updater(existing)
        write_manifest(path, updated)
        return updated


_REDACTED = "[REDACTED]"
_KEY_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")
_SENSITIVE_KEY_SUFFIXES = (
    "authorization",
    "api_key",
    "access_token",
    "client_secret",
    "token",
    "key",
)
_KEY_SEPARATOR_PATTERN = r"[_. -]+"
_TEXT_KEY = (
    rf"(?P<key>(?:[A-Za-z][A-Za-z0-9_. -]*?{_KEY_SEPARATOR_PATTERN})?"
    rf"(?:authorization|api{_KEY_SEPARATOR_PATTERN}key|"
    rf"access{_KEY_SEPARATOR_PATTERN}token|"
    rf"client{_KEY_SEPARATOR_PATTERN}secret|token|key))"
)
_QUOTED_VALUE_RE = re.compile(
    rf"(?P<prefix>(?<![\w.-])(?P<key_quote>[\"']?){_TEXT_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*(?P<value_quote>[\"']))"
    rf"(?P<value>.*?)(?P=value_quote)",
    re.IGNORECASE,
)
_AUTHORIZATION_VALUE_RE = re.compile(
    rf"(?P<prefix>(?<![\w.-])(?P<key_quote>[\"']?){_TEXT_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*)(?![\"'\[])"
    rf"(?P<value>[^\s,;&}}\]]+(?:\s+[^\s,;&}}\]]+)?)",
    re.IGNORECASE,
)
_AUTHORIZATION_SCHEME_RE = re.compile(
    r"(?P<prefix>(?<![\w.-])authorization\s+[A-Za-z][A-Za-z0-9_-]*\s+)"
    r"(?P<value>[^\s,;&}\]]+)",
    re.IGNORECASE,
)
_UNQUOTED_VALUE_RE = re.compile(
    rf"(?P<prefix>(?<![\w.-])(?P<key_quote>[\"']?){_TEXT_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*)(?![\"'\[])(?P<value>[^\s,;&}}\]]+)",
    re.IGNORECASE,
)
_SK_TOKEN_RE = re.compile(r"sk-[A-Za-z0-9_-]+", re.IGNORECASE)


def _normalize_sensitive_key(key: str) -> str:
    return _KEY_SEPARATOR_RE.sub("_", key.lower()).strip("_")


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_sensitive_key(key)
    return any(
        normalized == suffix or normalized.endswith(f"_{suffix}")
        for suffix in _SENSITIVE_KEY_SUFFIXES
    )


def _sanitize_sensitive_data(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: (
                _REDACTED
                if isinstance(key, str) and _is_sensitive_key(key)
                else _sanitize_sensitive_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_sensitive_data(item) for item in value)
    return value


def _error_text(message: object) -> str:
    sanitized = _sanitize_sensitive_data(message)
    if isinstance(message, BaseException):
        status = getattr(message, "status_code", None)
        status_text = "" if status is None else f" status={status}"
        return f"{type(message).__name__}{status_text}: {sanitized}"
    if isinstance(message, (Mapping, list, tuple)):
        return repr(sanitized)
    return str(sanitized)


def redact_error(message: object) -> str:
    """Return safe error text while retaining class, status, and ordinary context."""

    def redact_quoted(match: re.Match[str]) -> str:
        if not _is_sensitive_key(match.group("key")):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}{match.group('value_quote')}"

    def redact_authorization(match: re.Match[str]) -> str:
        if not _normalize_sensitive_key(match.group("key")).endswith("authorization"):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}"

    def redact_unquoted(match: re.Match[str]) -> str:
        if not _is_sensitive_key(match.group("key")):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}"

    redacted = _QUOTED_VALUE_RE.sub(redact_quoted, _error_text(message))
    redacted = _AUTHORIZATION_VALUE_RE.sub(redact_authorization, redacted)
    redacted = _AUTHORIZATION_SCHEME_RE.sub(rf"\g<prefix>{_REDACTED}", redacted)
    redacted = _UNQUOTED_VALUE_RE.sub(redact_unquoted, redacted)
    return _SK_TOKEN_RE.sub(_REDACTED, redacted)


def build_contract(
    *,
    collection: str,
    provider: str,
    model: str,
    git_head: str,
    schema_version: int,
    chunk_settings: dict,
) -> dict:
    """Construct the protected portion of a rebuild manifest."""
    contract = {
        "collection": collection,
        "provider": provider,
        "model": model,
        "git_head": git_head,
        "schema_version": schema_version,
        "chunk_settings": chunk_settings,
    }
    _validate_build_contract(contract, label="contract")
    contract["chunk_settings"] = dict(chunk_settings)
    return contract


def _validate_build_contract(contract: dict, *, label: str) -> None:
    if not isinstance(contract, dict):
        raise ValueError(f"{label} must be a build-contract object")
    for field in ("collection", "provider", "model", "git_head"):
        value = contract.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} field {field} must be a nonempty string")
    schema_version = contract.get("schema_version")
    if type(schema_version) is not int or schema_version <= 0:
        raise ValueError(
            f"{label} field schema_version must be a positive built-in int"
        )
    chunk_settings = contract.get("chunk_settings")
    if type(chunk_settings) is not dict:
        raise ValueError(f"{label} field chunk_settings must be an object")
    try:
        _validate_strict_json_value(chunk_settings)
    except ValueError as exc:
        raise ValueError(
            f"{label} field chunk_settings must contain strict JSON-safe values"
        ) from exc


def _validate_strict_json_value(value: object) -> None:
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not isfinite(value):
            raise ValueError("floating-point values must be finite")
        return
    if type(value) is list:
        for item in value:
            _validate_strict_json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("mapping keys must be strings")
            _validate_strict_json_value(item)
        return
    raise ValueError(f"unsupported JSON value type: {type(value).__name__}")


def validate_resume_contract(existing: dict, requested: dict) -> None:
    """Reject a resume when any protected build-contract field has changed."""
    _validate_build_contract(existing, label="existing contract")
    _validate_build_contract(requested, label="requested contract")
    mismatches = [
        field
        for field in PROTECTED_CONTRACT_FIELDS
        if existing.get(field) != requested.get(field)
    ]
    if mismatches:
        raise ValueError(f"Resume contract mismatch: {', '.join(mismatches)}")


def create_build_manifest(*, metadata_dir: Path, contract: dict) -> dict:
    """Create Task 6's initial manifest without parsing source payloads.

    Schema: status; the six protected contract fields; ordered sources containing
    metadata-directory-relative POSIX paths and SHA-256 hashes; per-paper state;
    source_count; and chunk_count.
    """
    _validate_build_contract(contract, label="contract")
    sources = discover_parsed_sources(metadata_dir)
    source_records = [
        {
            "path": source.relative_to(metadata_dir).as_posix(),
            "sha256": source_sha256(source),
        }
        for source in sources
    ]
    protected = {field: contract[field] for field in PROTECTED_CONTRACT_FIELDS}
    return {
        "status": "building",
        **protected,
        "sources": source_records,
        "papers": {},
        "source_count": len(source_records),
        "chunk_count": 0,
    }


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive built-in int")
    return value


def _nonnegative_finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a nonnegative finite number")
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0:
        raise ValueError(f"{label} must be a nonnegative finite number")
    return normalized


def _retry_after_seconds(
    exc: Exception, *, now: Callable[[], datetime]
) -> float | None:
    candidate = getattr(exc, "retry_after", None)
    if candidate is None:
        headers = getattr(exc, "headers", None)
        if isinstance(headers, Mapping):
            candidate = next(
                (
                    value
                    for key, value in headers.items()
                    if str(key).lower() == "retry-after"
                ),
                None,
            )
    if candidate is None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if isinstance(headers, Mapping):
            candidate = next(
                (
                    value
                    for key, value in headers.items()
                    if str(key).lower() == "retry-after"
                ),
                None,
            )
    try:
        delay = float(candidate)
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(str(candidate))
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        current = now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        delay = max(0.0, (retry_at - current).total_seconds())
    return delay if isfinite(delay) and delay >= 0 else None


def _retryable_embedding_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return (
        status_code in {429, 500, 502, 503, 504}
        or isinstance(exc, TimeoutError)
        or type(exc).__name__
        in {
            "APITimeoutError",
            "TimeoutException",
            "ConnectTimeout",
            "ReadTimeout",
            "WriteTimeout",
            "PoolTimeout",
        }
    )


def embed_batch_with_retry(
    client,
    texts: list[str],
    *,
    max_attempts: int,
    base_delay: float,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[list[float]]:
    """Embed one batch with bounded retry for transient provider failures."""
    _positive_int(max_attempts, "max_attempts")
    base_delay = _nonnegative_finite(base_delay, "base_delay")
    for attempt in range(1, max_attempts + 1):
        try:
            return client.embed_texts(texts)
        except Exception as exc:
            if not _retryable_embedding_error(exc) or attempt == max_attempts:
                raise
            delay = _retry_after_seconds(exc, now=now)
            if delay is None:
                delay = base_delay * 2 ** (attempt - 1)
            sleep(delay)
    raise AssertionError("retry loop exited unexpectedly")


def _captured_source(path: Path) -> tuple[bytes, str]:
    """Read one stable byte snapshot and return it with its digest."""
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        payload = handle.read()
        after = os.fstat(handle.fileno())
    current = path.stat()
    signatures = {
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns),
    }
    if len(signatures) != 1:
        raise RuntimeError(f"Source {path.name!r} changed while being read")
    return payload, hashlib.sha256(payload).hexdigest()


def _resolve_manifest_source(metadata_dir: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("manifest source path must be a nonempty relative path")
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
        raise ValueError(
            f"manifest source path escapes metadata directory: {relative!r}"
        )
    root = metadata_dir.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"manifest source path escapes metadata directory: {relative!r}"
        ) from exc
    return resolved


def _validate_manifest_source_records(
    *,
    manifest: dict,
    metadata_dir: Path,
    sources: list[Path],
    expected_source_count: int,
) -> None:
    records = manifest.get("sources")
    if not isinstance(records, list) or len(records) != expected_source_count:
        raise ValueError("manifest sources do not match expected source count")
    if manifest.get("source_count") != expected_source_count:
        raise ValueError("manifest source_count does not match expected source count")
    resolved = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("manifest source record must be an object")
        digest = record.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None
        ):
            raise ValueError(
                "manifest source record sha256 must be a hexadecimal digest"
            )
        resolved.append(_resolve_manifest_source(metadata_dir, record.get("path")))
    if len(set(resolved)) != len(resolved):
        raise ValueError("manifest source paths must be unique")
    if {path.resolve() for path in sources} != set(resolved):
        raise ValueError("manifest sources do not match discovered parsed sources")
    if type(manifest.get("papers")) is not dict:
        raise ValueError("manifest papers must be an object")


def _discover_expected_sources(
    metadata_dir: Path, expected_source_count: int
) -> list[Path]:
    sources = discover_parsed_sources(metadata_dir)
    if len(sources) != expected_source_count:
        raise ValueError(
            f"Expected exactly {expected_source_count} parsed sources; found {len(sources)}"
        )
    return sources


def preflight_rebuild(
    *,
    metadata_dir: Path,
    manifest_path: Path,
    contract: dict,
    expected_source_count: int,
    require_manifest: bool = False,
) -> tuple[list[Path], dict | None]:
    """Validate sources and resume state without creating or changing artifacts."""
    expected_source_count = _positive_int(
        expected_source_count, "expected_source_count"
    )
    _validate_build_contract(contract, label="contract")
    metadata_dir = Path(metadata_dir)
    sources = _discover_expected_sources(metadata_dir, expected_source_count)
    manifest = load_manifest(Path(manifest_path))
    if manifest is None:
        if require_manifest:
            raise FileNotFoundError(
                f"Required rebuild manifest does not exist: {Path(manifest_path).name}"
            )
        return sources, None
    validate_resume_contract(manifest, contract)
    _validate_manifest_source_records(
        manifest=manifest,
        metadata_dir=metadata_dir,
        sources=sources,
        expected_source_count=expected_source_count,
    )
    return sources, manifest


class ChromaIndexRebuilder:
    """Build and verify a versioned Chroma collection with resumable state."""

    def __init__(
        self,
        *,
        metadata_dir: Path,
        manifest_path: Path,
        backend,
        embedding_client,
        batch_size: int,
        max_attempts: int,
        base_delay: float,
        git_head: str,
        chunk_settings: dict,
        expected_source_count: int,
        sleep: Callable[[float], None] = time.sleep,
        lock_timeout: float = _MANIFEST_LOCK_TIMEOUT_SECONDS,
    ):
        self.metadata_dir = Path(metadata_dir)
        self.manifest_path = Path(manifest_path)
        self.backend = backend
        self.embedding_client = embedding_client
        self.batch_size = _positive_int(batch_size, "batch_size")
        self.max_attempts = _positive_int(max_attempts, "max_attempts")
        self.base_delay = _nonnegative_finite(base_delay, "base_delay")
        self.expected_source_count = _positive_int(
            expected_source_count, "expected_source_count"
        )
        self.lock_timeout = _nonnegative_finite(lock_timeout, "lock_timeout")
        if not isinstance(git_head, str) or not git_head.strip():
            raise ValueError("git_head must be a nonempty string")
        if type(chunk_settings) is not dict:
            raise ValueError("chunk_settings must be an object")
        self.chunk_settings = dict(chunk_settings)
        if backend.backend_name() != "chroma":
            raise ValueError("rebuild backend must be chroma")
        collection = getattr(backend, "collection_name", None)
        if not isinstance(collection, str) or not collection.strip():
            raise ValueError("backend collection_name must be a nonempty string")
        if getattr(embedding_client, "provider", None) != "api":
            raise ValueError("embedding provider must be api")
        if getattr(embedding_client, "model_name", None) != "bge-m3":
            raise ValueError("embedding model must be bge-m3")
        collection_metadata = backend.metadata()
        if (
            collection_metadata.get("embedding_model") != "bge-m3"
            or type(collection_metadata.get("schema_version")) is not int
            or collection_metadata.get("schema_version") != 1
            or collection_metadata.get("build_status")
            not in {"building", "ready", "failed"}
        ):
            raise ValueError(
                "collection metadata must specify embedding_model='bge-m3', "
                "schema_version=1, and a valid build_status"
            )
        self.sleep = sleep
        self.contract = build_contract(
            collection=collection,
            provider="api",
            model="bge-m3",
            git_head=git_head,
            schema_version=1,
            chunk_settings=chunk_settings,
        )

    def _validated_sources(self) -> list[Path]:
        return _discover_expected_sources(self.metadata_dir, self.expected_source_count)

    def _resolve_source_path(self, relative: object) -> Path:
        return _resolve_manifest_source(self.metadata_dir, relative)

    def _validate_manifest_sources(self, manifest: dict, sources: list[Path]) -> None:
        _validate_manifest_source_records(
            manifest=manifest,
            metadata_dir=self.metadata_dir,
            sources=sources,
            expected_source_count=self.expected_source_count,
        )

    def _load_or_create_manifest(
        self, sources: list[Path], *, require_manifest: bool = False
    ) -> dict:
        preflight_sources, manifest = preflight_rebuild(
            metadata_dir=self.metadata_dir,
            manifest_path=self.manifest_path,
            contract=self.contract,
            expected_source_count=self.expected_source_count,
            require_manifest=require_manifest,
        )
        if {path.resolve() for path in preflight_sources} != {
            path.resolve() for path in sources
        }:
            raise RuntimeError("Parsed sources changed during rebuild preflight")
        if manifest is None:
            manifest = create_build_manifest(
                metadata_dir=self.metadata_dir, contract=self.contract
            )
            write_manifest(self.manifest_path, manifest)
        self._validate_manifest_sources(manifest, sources)
        return manifest

    @staticmethod
    def _paper_for_source(manifest: dict, source_name: str) -> tuple[str, dict] | None:
        for paper_id, record in manifest["papers"].items():
            if isinstance(record, dict) and record.get("source_path") == source_name:
                return paper_id, record
        return None

    def _should_skip(self, manifest: dict, source: Path) -> bool:
        found = self._paper_for_source(manifest, source.name)
        if found is None:
            return False
        paper_id, record = found
        _, digest = _captured_source(source)
        expected_ids = record.get("expected_ids")
        return (
            record.get("status") == "completed"
            and record.get("sha256") == digest
            and isinstance(expected_ids, list)
            and len(expected_ids) == len(set(expected_ids))
            and set(expected_ids) == self.backend.ids_for_paper(paper_id)
        )

    def _record_failure(
        self, manifest: dict, source: Path, exc: Exception, paper_id: str | None
    ) -> None:
        manifest["status"] = "failed"
        safe_error = redact_error(exc)
        if paper_id is None:
            failures = manifest.setdefault("failures", {})
            failures[source.name] = safe_error
        else:
            prior = manifest["papers"].get(paper_id, {})
            manifest["papers"][paper_id] = {
                **prior,
                "source_path": source.name,
                "status": "failed",
                "error": safe_error,
            }
        write_manifest(self.manifest_path, manifest)

    def _process_source(self, manifest: dict, source: Path) -> None:
        paper_id: str | None = None
        try:
            payload, digest = _captured_source(source)
            parsed = PaperParseResult.model_validate_json(payload.decode("utf-8"))
            paper_id = parsed.paper_id
            chunks = chunk_paper(
                parsed,
                chunk_size=self.chunk_settings.get("size", 500),
                chunk_overlap=self.chunk_settings.get("overlap", 100),
            )
            if not chunks:
                raise ValueError(f"Paper {paper_id!r} produced no chunks")
            expected_ids = [chunk.chunk_id for chunk in chunks]
            if len(expected_ids) != len(set(expected_ids)):
                raise ValueError(f"Paper {paper_id!r} produced duplicate chunk IDs")
            embeddings: list[list[float]] = []
            locked_dimension = self.backend.metadata().get("embedding_dimension")
            for offset in range(0, len(chunks), self.batch_size):
                batch = chunks[offset : offset + self.batch_size]
                batch_embeddings = embed_batch_with_retry(
                    self.embedding_client,
                    [chunk.content for chunk in batch],
                    max_attempts=self.max_attempts,
                    base_delay=self.base_delay,
                    sleep=self.sleep,
                )
                dimension = validate_embeddings(
                    batch,
                    batch_embeddings,
                    expected_dimension=locked_dimension,
                )
                if locked_dimension is None:
                    locked_dimension = dimension
                    self.backend.update_build_metadata(
                        {"embedding_dimension": locked_dimension}
                    )
                embeddings.extend(batch_embeddings)
            dimension = validate_embeddings(
                chunks, embeddings, expected_dimension=locked_dimension
            )
            if source_sha256(source) != digest:
                raise RuntimeError(f"Source {source.name!r} changed during processing")

            previous = self._paper_for_source(manifest, source.name)
            if previous is not None and previous[1].get("sha256") != digest:
                self.backend.delete_paper(previous[0])
            self.backend.add_chunks(chunks, embeddings)
            live_ids = self.backend.ids_for_paper(paper_id)
            if live_ids != set(expected_ids):
                raise RuntimeError(
                    f"Chroma IDs for {paper_id!r} do not exactly match expected IDs"
                )
            if source_sha256(source) != digest:
                raise RuntimeError(f"Source {source.name!r} changed during processing")

            if previous is not None and previous[0] != paper_id:
                manifest["papers"].pop(previous[0], None)
            manifest["papers"][paper_id] = {
                "source_path": source.name,
                "sha256": digest,
                "status": "completed",
                "expected_ids": sorted(expected_ids),
                "chunk_count": len(expected_ids),
                "embedding_dimension": dimension,
            }
            for record in manifest["sources"]:
                if record["path"] == source.name:
                    record["sha256"] = digest
            manifest.pop("failures", None)
            manifest["status"] = "building"
            manifest["chunk_count"] = sum(
                record.get("chunk_count", 0)
                for record in manifest["papers"].values()
                if record.get("status") == "completed"
            )
            write_manifest(self.manifest_path, manifest)
        except Exception as exc:
            self._record_failure(manifest, source, exc, paper_id)
            raise

    def _verify(self, manifest: dict, *, require_complete: bool) -> dict:
        sources = self._validated_sources()
        self._validate_manifest_sources(manifest, sources)
        status = manifest.get("status")
        if status not in {"building", "ready"}:
            raise RuntimeError(f"Manifest status {status!r} is not verifiable")
        source_records = {record["path"]: record for record in manifest["sources"]}
        completed = {
            paper_id: record
            for paper_id, record in manifest["papers"].items()
            if isinstance(record, dict) and record.get("status") == "completed"
        }
        if require_complete and len(completed) != self.expected_source_count:
            raise RuntimeError(
                f"Rebuild incomplete: {len(completed)}/{self.expected_source_count} papers"
            )
        expected_ids: set[str] = set()
        completed_source_paths: set[str] = set()
        for paper_id, record in completed.items():
            source_path = record.get("source_path")
            if source_path not in source_records:
                raise RuntimeError(
                    f"Completed paper {paper_id!r} has no current source record"
                )
            if source_path in completed_source_paths:
                raise RuntimeError(
                    f"Completed papers have duplicate source association {source_path!r}"
                )
            completed_source_paths.add(source_path)
            source_digest = source_records[source_path].get("sha256")
            _, current_digest = _captured_source(self._resolve_source_path(source_path))
            if record.get("sha256") != source_digest or source_digest != current_digest:
                raise RuntimeError(
                    f"Completed paper {paper_id!r} source hash is not current"
                )
            ids = record.get("expected_ids")
            if not isinstance(ids, list) or len(ids) != len(set(ids)):
                raise RuntimeError(f"Manifest IDs for {paper_id!r} are invalid")
            if set(ids) != self.backend.ids_for_paper(paper_id):
                raise RuntimeError(f"Live IDs for {paper_id!r} do not match manifest")
            if expected_ids.intersection(ids):
                raise RuntimeError("Chunk IDs are not unique across papers")
            expected_ids.update(ids)
        if require_complete and completed_source_paths != set(source_records):
            raise RuntimeError(
                "Completed papers are not a bijection with current source records"
            )

        rows = self.backend.list_chunks()
        live_ids = [row["chunk_id"] for row in rows]
        if len(live_ids) != len(set(live_ids)):
            raise RuntimeError("Chroma contains duplicate chunk IDs")
        if set(live_ids) != expected_ids:
            raise RuntimeError(
                "Chroma chunk IDs do not match completed manifest papers"
            )
        dimensions = {row.get("embedding_dim") for row in rows}
        if rows and (len(dimensions) != 1 or next(iter(dimensions)) <= 0):
            raise RuntimeError("Chroma embeddings do not have one valid dimension")
        metadata = self.backend.metadata()
        if metadata.get("build_status") != status:
            raise RuntimeError(
                "Chroma collection is not ready or its build status is inconsistent "
                "with the manifest"
            )
        dimension = metadata.get("embedding_dimension")
        if rows and dimensions != {dimension}:
            raise RuntimeError("Chroma embedding dimension does not match metadata")
        for paper_id, record in completed.items():
            if record.get("embedding_dimension") != dimension:
                raise RuntimeError(
                    f"Completed paper {paper_id!r} embedding dimension does not "
                    "match Chroma metadata"
                )
        paper_ids = {row.get("paper_id") for row in rows}
        result = {
            "status": status,
            "completed_paper_count": len(completed),
            "paper_count": len(paper_ids),
            "chunk_count": len(rows),
            "embedding_dimension": dimension,
        }
        if require_complete and (
            result["paper_count"] != self.expected_source_count
            or result["chunk_count"]
            != sum(r["chunk_count"] for r in completed.values())
        ):
            raise RuntimeError("Verified paper or chunk counts do not match manifest")
        if status == "ready" and len(completed) != self.expected_source_count:
            raise RuntimeError("Ready manifest does not cover every source")
        return result

    def run_canary(self) -> dict:
        with manifest_write_lock(self.manifest_path, timeout=self.lock_timeout):
            sources = self._validated_sources()
            manifest = self._load_or_create_manifest(sources)
            canary = sorted(sources, key=lambda path: (path.stat().st_size, path.name))[
                len(sources) // 2
            ]
            if not self._should_skip(manifest, canary):
                manifest["status"] = "building"
                write_manifest(self.manifest_path, manifest)
                self.backend.update_build_metadata({"build_status": "building"})
                self._process_source(manifest, canary)
            return self._verify(manifest, require_complete=False)

    def run_all(self) -> dict:
        with manifest_write_lock(self.manifest_path, timeout=self.lock_timeout):
            sources = self._validated_sources()
            manifest = self._load_or_create_manifest(sources)
            manifest["status"] = "building"
            write_manifest(self.manifest_path, manifest)
            self.backend.update_build_metadata({"build_status": "building"})
            if not any(
                record.get("status") == "completed"
                for record in manifest["papers"].values()
            ):
                canary = sorted(
                    sources, key=lambda path: (path.stat().st_size, path.name)
                )[len(sources) // 2]
                self._process_source(manifest, canary)
            for source in sources:
                if not self._should_skip(manifest, source):
                    self._process_source(manifest, source)
            result = self._verify(manifest, require_complete=True)
            manifest.update(result)
            manifest["status"] = "ready"
            write_manifest(self.manifest_path, manifest)
            self.backend.update_build_metadata({"build_status": "ready"})
            return {**result, "status": "ready"}

    def verify(self, *, require_complete: bool = True) -> dict:
        with manifest_write_lock(self.manifest_path, timeout=self.lock_timeout):
            sources = self._validated_sources()
            manifest = self._load_or_create_manifest(sources, require_manifest=True)
            result = self._verify(manifest, require_complete=require_complete)
            if require_complete and manifest.get("status") != "ready":
                raise RuntimeError("Manifest is not ready")
            if (
                require_complete
                and self.backend.metadata().get("build_status") != "ready"
            ):
                raise RuntimeError("Chroma collection is not ready")
            return result
