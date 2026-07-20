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
