import json
from pathlib import Path

import pytest

from app.services.chroma_rebuild import (
    build_contract,
    create_build_manifest,
    discover_parsed_sources,
    load_manifest,
    redact_error,
    source_sha256,
    validate_resume_contract,
    write_manifest,
)


def test_discover_parsed_sources_returns_only_matching_files_sorted_by_name(
    tmp_path: Path,
):
    second = tmp_path / "paper_b_parsed.json"
    first = tmp_path / "paper_a_parsed.json"
    second.write_text('{"paper_id":"b"}', encoding="utf-8")
    first.write_text('{"paper_id":"a"}', encoding="utf-8")
    (tmp_path / "paper.json").write_text("{}", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "paper_c_parsed.json").write_text("{}", encoding="utf-8")
    (tmp_path / "not_a_file_parsed.json").mkdir()

    assert discover_parsed_sources(tmp_path) == [first, second]


def test_discover_parsed_sources_rejects_symlink_outside_metadata_root(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    outside = tmp_path / "outside_parsed.json"
    outside.write_text("{}", encoding="utf-8")
    link = metadata_dir / "linked_parsed.json"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    with pytest.raises(ValueError, match="outside metadata directory"):
        discover_parsed_sources(metadata_dir)


def test_source_sha256_is_stable_and_changes_with_large_file_content(tmp_path: Path):
    source = tmp_path / "large_parsed.json"
    source.write_bytes(b"a" * (1024 * 1024 + 17))

    original = source_sha256(source)

    assert source_sha256(source) == original
    source.write_bytes(b"a" * (1024 * 1024 + 16) + b"b")
    assert source_sha256(source) != original


def test_manifest_write_is_utf8_indented_and_round_trips(tmp_path: Path):
    path = tmp_path / "nested" / "manifest.json"
    manifest = {"状态": "构建中", "papers": {"论文": {"标题": "向量检索"}}}

    write_manifest(path, manifest)

    raw = path.read_bytes()
    assert b"\n  " in raw
    assert b"\\u" not in raw
    assert json.loads(raw.decode("utf-8")) == manifest
    assert load_manifest(path) == manifest


def test_load_manifest_returns_none_only_when_file_is_missing(tmp_path: Path):
    assert load_manifest(tmp_path / "missing.json") is None

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_manifest(malformed)


def test_load_manifest_does_not_treat_existing_directory_as_missing(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.mkdir()

    with pytest.raises(OSError):
        load_manifest(path)


@pytest.mark.parametrize("payload", ["[]", '"manifest"', "null"])
def test_load_manifest_rejects_non_object_json(tmp_path: Path, payload: str):
    path = tmp_path / "manifest.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="top-level JSON object"):
        load_manifest(path)


def test_error_redaction_removes_credentials_and_preserves_context():
    message = (
        "request failed: Authorization: Bearer bearer-token-value; "
        "API_KEY=api-value, key: plain-key-value, upstream sk-token-value timed out"
    )

    redacted = redact_error(message)

    for credential in (
        "bearer-token-value",
        "api-value",
        "plain-key-value",
        "sk-token-value",
    ):
        assert credential not in redacted
    assert "request failed" in redacted
    assert "upstream" in redacted
    assert "timed out" in redacted
    assert redacted.count("[REDACTED]") == 4


def test_validate_resume_contract_accepts_equal_protected_fields():
    contract = build_contract(
        collection="research_papers_bge_m3_v1",
        provider="api",
        model="bge-m3",
        git_head="abc",
        schema_version=1,
        chunk_settings={"strategy": "parent_child", "size": 500, "overlap": 100},
    )

    validate_resume_contract(
        {**contract, "status": "building", "papers": {}},
        {**contract, "status": "requested"},
    )


def test_validate_resume_contract_names_all_mismatched_fields_deterministically():
    existing = build_contract(
        collection="old_collection",
        provider="local",
        model="old-model",
        git_head="old-head",
        schema_version=1,
        chunk_settings={"strategy": "old", "size": 500},
    )
    requested = build_contract(
        collection="new_collection",
        provider="api",
        model="bge-m3",
        git_head="new-head",
        schema_version=2,
        chunk_settings={"strategy": "new", "size": 500},
    )

    with pytest.raises(ValueError) as caught:
        validate_resume_contract(existing, requested)

    assert str(caught.value) == (
        "Resume contract mismatch: collection, provider, model, git_head, "
        "schema_version, chunk_settings"
    )


def test_create_build_manifest_has_documented_deterministic_schema(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    second = metadata_dir / "论文_b_parsed.json"
    first = metadata_dir / "paper_a_parsed.json"
    second.write_text('{"paper_id":"b"}', encoding="utf-8")
    first.write_text('{"paper_id":"a"}', encoding="utf-8")
    contract = build_contract(
        collection="research_papers_bge_m3_v1",
        provider="api",
        model="bge-m3",
        git_head="abc123",
        schema_version=1,
        chunk_settings={"strategy": "parent_child", "size": 500, "overlap": 100},
    )

    manifest = create_build_manifest(metadata_dir=metadata_dir, contract=contract)

    assert manifest == {
        "status": "building",
        "collection": "research_papers_bge_m3_v1",
        "provider": "api",
        "model": "bge-m3",
        "git_head": "abc123",
        "schema_version": 1,
        "chunk_settings": {
            "strategy": "parent_child",
            "size": 500,
            "overlap": 100,
        },
        "sources": [
            {"path": "paper_a_parsed.json", "sha256": source_sha256(first)},
            {"path": "论文_b_parsed.json", "sha256": source_sha256(second)},
        ],
        "papers": {},
        "source_count": 2,
        "chunk_count": 0,
    }


def test_atomic_write_failure_preserves_prior_manifest_and_cleans_temp(
    tmp_path: Path, monkeypatch
):
    path = tmp_path / "manifest.json"
    write_manifest(path, {"status": "old"})
    before = path.read_bytes()

    def fail_replace(_source, _destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr("app.services.chroma_rebuild.os.replace", fail_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        write_manifest(path, {"status": "new"})

    assert path.read_bytes() == before
    assert list(tmp_path.glob(".manifest.json.*.tmp")) == []


def test_write_manifest_rejects_non_object_before_creating_parent_or_temp(
    tmp_path: Path,
):
    path = tmp_path / "new" / "manifest.json"

    with pytest.raises(ValueError, match="top-level.*object"):
        write_manifest(path, ["not", "an", "object"])

    assert path.parent.exists() is False


def test_manifest_serialization_failure_preserves_prior_bytes_and_cleans_temp(
    tmp_path: Path,
):
    path = tmp_path / "manifest.json"
    write_manifest(path, {"status": "old"})
    before = path.read_bytes()

    with pytest.raises(ValueError, match="JSON compliant"):
        write_manifest(path, {"score": float("nan")})

    assert path.read_bytes() == before
    assert list(tmp_path.glob(".manifest.json.*.tmp")) == []


@pytest.mark.parametrize(
    "message",
    [
        "status=429 request failed headers={'Authorization': 'Bearer synthetic-secret'} retrying",
        "status=429 request failed Authorization Bearer synthetic-secret retrying",
        'status=429 request failed body={"api_key":"synthetic-secret"} retrying',
        "status=429 request failed authorization=Bearer synthetic-secret retrying",
        "status=429 request failed url=/embed?access_token=synthetic-secret&mode=batch retrying",
        "status=429 request failed client_secret=synthetic-secret retrying",
        "status=429 request failed token=synthetic-secret retrying",
        "status=429 request failed prefix=foo_sk-synthetic retrying",
    ],
)
def test_error_redaction_handles_common_request_and_exception_text(message: str):
    redacted = redact_error(message)

    assert "synthetic-secret" not in redacted
    assert "status=429" in redacted
    assert "request failed" in redacted
    assert "retrying" in redacted
    assert "[REDACTED]" in redacted


def test_error_redaction_recursively_sanitizes_structured_values():
    message = {
        "status": 429,
        "headers": {"Authorization": "Bearer synthetic-secret"},
        "items": [
            {"api-key": "synthetic-secret"},
            {"access_token": "synthetic-secret", "token_count": 17},
        ],
        "context": ({"client-secret": "synthetic-secret"}, "ordinary context"),
    }

    redacted = redact_error(message)

    assert isinstance(redacted, str)
    assert "synthetic-secret" not in redacted
    assert "429" in redacted
    assert "token_count" in redacted
    assert "17" in redacted
    assert "ordinary context" in redacted
    assert redacted.count("[REDACTED]") == 4


def test_error_redaction_retains_exception_class_status_and_context():
    error = RuntimeError(
        "status=503 request failed token=synthetic-secret; retry possible"
    )

    redacted = redact_error(error)

    assert redacted.startswith("RuntimeError: ")
    assert "status=503" in redacted
    assert "request failed" in redacted
    assert "retry possible" in redacted
    assert "synthetic-secret" not in redacted


def _valid_contract() -> dict:
    return {
        "collection": "research_papers_bge_m3_v1",
        "provider": "api",
        "model": "bge-m3",
        "git_head": "abc123",
        "schema_version": 1,
        "chunk_settings": {"strategy": "parent_child", "size": 500},
    }


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("collection", ""),
        ("provider", 7),
        ("model", "   "),
        ("git_head", None),
        ("schema_version", 0),
        ("chunk_settings", []),
    ],
)
def test_validate_resume_contract_rejects_malformed_equal_contracts(
    field: str, invalid_value
):
    malformed = {**_valid_contract(), field: invalid_value}

    with pytest.raises(ValueError, match=field):
        validate_resume_contract(malformed, malformed.copy())


def test_validate_resume_contract_rejects_missing_protected_field():
    malformed = _valid_contract()
    malformed.pop("provider")

    with pytest.raises(ValueError, match="provider"):
        validate_resume_contract(malformed, malformed.copy())


def test_validate_resume_contract_rejects_bool_schema_version_not_equal_to_one():
    requested = {**_valid_contract(), "schema_version": True}

    with pytest.raises(ValueError, match="schema_version"):
        validate_resume_contract(_valid_contract(), requested)


@pytest.mark.parametrize(
    "invalid_value",
    [float("nan"), float("inf"), {"not-json-safe"}],
)
def test_validate_resume_contract_rejects_non_json_safe_chunk_settings(
    invalid_value,
):
    malformed = {
        **_valid_contract(),
        "chunk_settings": {"invalid": invalid_value},
    }

    with pytest.raises(ValueError, match="chunk_settings"):
        validate_resume_contract(malformed, malformed.copy())


def test_build_contract_uses_the_same_validation_rules():
    with pytest.raises(ValueError, match="schema_version"):
        build_contract(
            collection="research_papers_bge_m3_v1",
            provider="api",
            model="bge-m3",
            git_head="abc123",
            schema_version=True,
            chunk_settings={"size": 500},
        )


def test_build_contract_rejects_non_object_chunk_settings_before_coercion():
    with pytest.raises(ValueError, match="chunk_settings"):
        build_contract(
            collection="research_papers_bge_m3_v1",
            provider="api",
            model="bge-m3",
            git_head="abc123",
            schema_version=1,
            chunk_settings=[],
        )
