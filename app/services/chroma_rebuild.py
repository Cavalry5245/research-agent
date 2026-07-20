from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path


HASH_BLOCK_SIZE = 1024 * 1024
PROTECTED_CONTRACT_FIELDS = (
    "collection",
    "provider",
    "model",
    "git_head",
    "schema_version",
    "chunk_settings",
)


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
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must contain a top-level JSON object")
    return manifest


def write_manifest(path: Path, manifest: dict) -> None:
    """Atomically replace a UTF-8 JSON manifest after flushing it to disk."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must contain a top-level JSON object")
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
        os.replace(temporary, path)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            # Preserve the original write failure if the explicit temp cannot be cleaned.
            pass


_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "api-key",
        "access_token",
        "access-token",
        "client_secret",
        "client-secret",
        "token",
        "key",
    }
)
_SENSITIVE_KEY_PATTERN = (
    r"(?:api[_-]?key|access[_-]?token|client[_-]?secret|token|key)"
)
_BEARER_RE = re.compile(
    rf"(?P<prefix>(?<![\w-])[\"']?authorization[\"']?\s*(?:[:=]\s*)?"
    rf"[\"']?bearer\s+)(?P<secret>[^\s,;\"'&}}\]]+)",
    re.IGNORECASE,
)
_QUOTED_ASSIGNMENT_RE = re.compile(
    rf"(?P<prefix>(?<![\w-])(?P<key_quote>[\"']?)"
    rf"{_SENSITIVE_KEY_PATTERN}(?P=key_quote)\s*[:=]\s*"
    rf"(?P<value_quote>[\"']))(?P<secret>.*?)(?P=value_quote)",
    re.IGNORECASE,
)
_UNQUOTED_ASSIGNMENT_RE = re.compile(
    rf"(?P<prefix>(?<![\w-])[\"']?{_SENSITIVE_KEY_PATTERN}[\"']?"
    rf"\s*[:=]\s*)(?P<secret>[^\s,;&}}\]]+)",
    re.IGNORECASE,
)
_SK_TOKEN_RE = re.compile(r"sk-[A-Za-z0-9_-]+", re.IGNORECASE)


def _sanitize_sensitive_data(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: (
                _REDACTED
                if isinstance(key, str) and key.lower() in _SENSITIVE_KEYS
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
    redacted = _BEARER_RE.sub(rf"\g<prefix>{_REDACTED}", _error_text(message))

    def redact_quoted(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{_REDACTED}{match.group('value_quote')}"

    redacted = _QUOTED_ASSIGNMENT_RE.sub(redact_quoted, redacted)
    redacted = _UNQUOTED_ASSIGNMENT_RE.sub(
        rf"\g<prefix>{_REDACTED}", redacted
    )
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
    if not isinstance(chunk_settings, dict):
        raise ValueError(f"{label} field chunk_settings must be an object")
    try:
        json.dumps(chunk_settings, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{label} field chunk_settings must contain finite JSON-safe values"
        ) from exc


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
