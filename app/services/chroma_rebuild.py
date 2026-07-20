from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from math import isfinite
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
    manifest = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_non_finite_json_constant,
    )
    if not isinstance(manifest, dict):
        raise ValueError("manifest must contain a top-level JSON object")
    return manifest


def _reject_non_finite_json_constant(constant: str) -> None:
    raise ValueError(f"manifest contains non-finite JSON constant: {constant}")


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
        if not _normalize_sensitive_key(match.group("key")).endswith(
            "authorization"
        ):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}"

    def redact_unquoted(match: re.Match[str]) -> str:
        if not _is_sensitive_key(match.group("key")):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}"

    redacted = _QUOTED_VALUE_RE.sub(redact_quoted, _error_text(message))
    redacted = _AUTHORIZATION_VALUE_RE.sub(redact_authorization, redacted)
    redacted = _AUTHORIZATION_SCHEME_RE.sub(
        rf"\g<prefix>{_REDACTED}", redacted
    )
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
