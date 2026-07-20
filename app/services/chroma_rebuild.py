from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
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
    return sorted(
        (path for path in metadata_dir.glob("*_parsed.json") if path.is_file()),
        key=lambda path: path.name,
    )


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
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
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


_SECRET_VALUE = r'(?:"[^"\r\n]*"|\'[^\'\r\n]*\'|[^\s,;]+)'
_BEARER_RE = re.compile(
    rf"(authorization\s*:?\s*bearer)\s+{_SECRET_VALUE}", re.IGNORECASE
)
_KEY_ASSIGNMENT_RE = re.compile(
    rf"\b(api[_-]?key|key)(\s*[:=]\s*){_SECRET_VALUE}", re.IGNORECASE
)
_SK_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_-]+", re.IGNORECASE)


def redact_error(message: str) -> str:
    """Remove common API credential forms while retaining surrounding context."""
    redacted = _BEARER_RE.sub(r"\1 [REDACTED]", str(message))
    redacted = _KEY_ASSIGNMENT_RE.sub(r"\1\2[REDACTED]", redacted)
    return _SK_TOKEN_RE.sub("[REDACTED]", redacted)


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
    return {
        "collection": collection,
        "provider": provider,
        "model": model,
        "git_head": git_head,
        "schema_version": schema_version,
        "chunk_settings": dict(chunk_settings),
    }


def validate_resume_contract(existing: dict, requested: dict) -> None:
    """Reject a resume when any protected build-contract field has changed."""
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
