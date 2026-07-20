import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services.chroma_rebuild import (
    ChromaIndexRebuilder,
    build_contract,
    create_build_manifest,
    discover_parsed_sources,
    embed_batch_with_retry,
    load_manifest,
    manifest_read_lock,
    manifest_write_lock,
    preflight_rebuild,
    redact_error,
    source_sha256,
    update_manifest_locked,
    validate_resume_contract,
    write_manifest,
)
from app.schemas import PaperParseResult, Section
from app.services.vector_backends.chroma_backend import (
    ChromaVectorBackend,
    validate_existing_chroma_store,
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


def test_load_manifest_rejects_non_finite_json_constant(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text('{"score": NaN}', encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite JSON constant"):
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


def test_preflight_rejects_source_count_without_creating_manifest(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(ValueError, match="Expected exactly 1 parsed sources"):
        preflight_rebuild(
            metadata_dir=metadata_dir,
            manifest_path=manifest_path,
            contract=_valid_contract(),
            expected_source_count=1,
        )

    assert not manifest_path.exists()


def test_verify_preflight_requires_existing_manifest_without_creating_it(
    tmp_path: Path,
):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1")
    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(FileNotFoundError, match="manifest"):
        preflight_rebuild(
            metadata_dir=metadata_dir,
            manifest_path=manifest_path,
            contract=_valid_contract(),
            expected_source_count=1,
            require_manifest=True,
        )

    assert not manifest_path.exists()


def test_preflight_rejects_resume_contract_before_any_mutation(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1")
    manifest_path = tmp_path / "manifest.json"
    stale = create_build_manifest(metadata_dir=metadata_dir, contract=_valid_contract())
    stale["model"] = "wrong-model"
    write_manifest(manifest_path, stale)
    before = manifest_path.read_bytes()

    with pytest.raises(ValueError, match="Resume contract mismatch: model"):
        preflight_rebuild(
            metadata_dir=metadata_dir,
            manifest_path=manifest_path,
            contract=_valid_contract(),
            expected_source_count=1,
        )

    assert manifest_path.read_bytes() == before


def test_preflight_rejects_unsafe_manifest_source_path_read_only(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1")
    manifest_path = tmp_path / "manifest.json"
    manifest = create_build_manifest(
        metadata_dir=metadata_dir, contract=_valid_contract()
    )
    manifest["sources"][0]["path"] = "../escape_parsed.json"
    write_manifest(manifest_path, manifest)
    before = manifest_path.read_bytes()

    with pytest.raises(ValueError, match="source path"):
        preflight_rebuild(
            metadata_dir=metadata_dir,
            manifest_path=manifest_path,
            contract=_valid_contract(),
            expected_source_count=1,
            require_manifest=True,
        )

    assert manifest_path.read_bytes() == before


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


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("X-API-Key: secret-value", "secret-value"),
        ("X-LLM-API-Key: secret-value", "secret-value"),
        ("OPENAI_API_KEY=secret-value", "secret-value"),
        ("EMBEDDING_API_KEY=secret-value", "secret-value"),
        ("LLM_API_KEY=secret-value", "secret-value"),
        ("SEMANTIC_SCHOLAR_API_KEY=secret-value", "secret-value"),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
    ],
)
def test_error_redaction_covers_provider_keys_and_any_authorization_scheme(
    message: str, secret: str
):
    redacted = redact_error(message)

    assert secret not in redacted
    assert redacted.endswith("[REDACTED]")


def test_error_redaction_keeps_json_shaped_context_well_formed():
    redacted = redact_error('{"api_key": "secret-value"}')

    assert redacted == '{"api_key": "[REDACTED]"}'
    assert json.loads(redacted) == {"api_key": "[REDACTED]"}


def test_error_redaction_normalizes_structured_key_suffixes_and_separators():
    message = {
        "X-API-Key": "secret-one",
        "x.llm.api.key": "secret-two",
        "OPENAI_API_KEY": "secret-three",
        "Nested": [{"Semantic Scholar API Key": "secret-four"}],
        "token_count": 23,
    }

    redacted = redact_error(message)

    for secret in ("secret-one", "secret-two", "secret-three", "secret-four"):
        assert secret not in redacted
    assert "token_count" in redacted
    assert "23" in redacted


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


@pytest.mark.parametrize(
    "chunk_settings",
    [
        {1: "non-string-key"},
        {"nested": ("tuple", "changes-to-list")},
    ],
)
def test_validate_resume_contract_requires_round_trip_stable_chunk_types(
    chunk_settings,
):
    malformed = {**_valid_contract(), "chunk_settings": chunk_settings}

    with pytest.raises(ValueError, match="chunk_settings"):
        validate_resume_contract(malformed, malformed.copy())


def test_validate_resume_contract_accepts_nested_strict_json_chunk_settings():
    contract = {
        **_valid_contract(),
        "chunk_settings": {
            "strategies": ["parent", None, True, 2, 0.5],
            "nested": {"overlap": 100},
        },
    }

    validate_resume_contract(contract, json.loads(json.dumps(contract)))


class RetryableEmbeddingError(RuntimeError):
    status_code = 429


class FakeEmbeddingClient:
    provider = "api"
    model_name = "bge-m3"

    def __init__(self, failures: int = 0, error_factory=None):
        self.failures = failures
        self.error_factory = error_factory or (
            lambda: RetryableEmbeddingError("rate limited")
        )
        self.calls = 0

    def embed_texts(self, texts):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error_factory()
        return [[float(index + 1), 0.0, 1.0] for index, _ in enumerate(texts)]


def _write_parsed_fixture(
    metadata_dir: Path, paper_id: str, *, repeat: int = 80
) -> Path:
    parsed = PaperParseResult(
        paper_id=paper_id,
        title=f"Title {paper_id}",
        abstract=f"Abstract for {paper_id}",
        sections=[Section(heading="Methods", content="method details " * repeat)],
        full_text=f"Abstract for {paper_id}\n" + "method details " * repeat,
    )
    path = metadata_dir / f"{paper_id}_parsed.json"
    path.write_text(parsed.model_dump_json(), encoding="utf-8")
    return path


def _rebuilder(tmp_path: Path, metadata_dir: Path, backend, client, *, expected=2):
    return ChromaIndexRebuilder(
        metadata_dir=metadata_dir,
        manifest_path=tmp_path / "rebuild_manifest.json",
        backend=backend,
        embedding_client=client,
        batch_size=2,
        max_attempts=3,
        base_delay=0.01,
        git_head="test-head",
        chunk_settings={
            "strategy": "parent_child_sliding_window",
            "size": 500,
            "overlap": 100,
        },
        expected_source_count=expected,
        sleep=lambda _delay: None,
    )


def test_embed_batch_retries_429_with_retry_after_then_exponential_delay():
    class WithHeaders(RetryableEmbeddingError):
        headers = {"Retry-After": "0.75"}

    client = FakeEmbeddingClient(failures=2, error_factory=WithHeaders)
    sleeps = []

    vectors = embed_batch_with_retry(
        client, ["a", "b"], max_attempts=3, base_delay=0.25, sleep=sleeps.append
    )

    assert len(vectors) == 2
    assert client.calls == 3
    assert sleeps == [0.75, 0.75]


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_embed_batch_retries_transient_provider_statuses(status):
    error_type = type("ProviderError", (RuntimeError,), {"status_code": status})
    client = FakeEmbeddingClient(
        failures=1, error_factory=lambda: error_type("secret token=hidden")
    )

    assert embed_batch_with_retry(
        client, ["a"], max_attempts=2, base_delay=0, sleep=lambda _: None
    )
    assert client.calls == 2


def test_embed_batch_retries_generic_provider_timeout_type():
    class TimeoutException(RuntimeError):
        pass

    client = FakeEmbeddingClient(failures=1, error_factory=TimeoutException)

    assert embed_batch_with_retry(
        client, ["a"], max_attempts=2, base_delay=0, sleep=lambda _: None
    )
    assert client.calls == 2


def test_embed_batch_rejects_invalid_retry_arguments_and_retry_after():
    class InvalidRetryAfter(RetryableEmbeddingError):
        retry_after = "NaN"

    with pytest.raises(ValueError, match="max_attempts"):
        embed_batch_with_retry(
            FakeEmbeddingClient(), ["a"], max_attempts=True, base_delay=0
        )
    with pytest.raises(ValueError, match="base_delay"):
        embed_batch_with_retry(
            FakeEmbeddingClient(), ["a"], max_attempts=2, base_delay=float("inf")
        )

    sleeps = []
    embed_batch_with_retry(
        FakeEmbeddingClient(failures=1, error_factory=InvalidRetryAfter),
        ["a"],
        max_attempts=2,
        base_delay=0.5,
        sleep=sleeps.append,
    )
    assert sleeps == [0.5]


def test_embed_batch_honors_rfc_http_date_retry_after():
    now = datetime(2026, 7, 21, 4, 0, 0, tzinfo=timezone.utc)

    class DatedRetry(RetryableEmbeddingError):
        headers = {
            "Retry-After": (now + timedelta(seconds=7)).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
        }

    sleeps = []
    embed_batch_with_retry(
        FakeEmbeddingClient(failures=1, error_factory=DatedRetry),
        ["a"],
        max_attempts=2,
        base_delay=0.5,
        sleep=sleeps.append,
        now=lambda: now,
    )

    assert sleeps == [7.0]


def test_embed_batch_treats_past_rfc_http_date_retry_after_as_zero():
    now = datetime(2026, 7, 21, 4, 0, 0, tzinfo=timezone.utc)

    class PastDatedRetry(RetryableEmbeddingError):
        headers = {
            "Retry-After": (now - timedelta(seconds=7)).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
        }

    sleeps = []
    embed_batch_with_retry(
        FakeEmbeddingClient(failures=1, error_factory=PastDatedRetry),
        ["a"],
        max_attempts=2,
        base_delay=0.5,
        sleep=sleeps.append,
        now=lambda: now,
    )

    assert sleeps == [0.0]


def test_rebuild_canary_full_run_and_no_cost_resume(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1", repeat=20)
    _write_parsed_fixture(metadata_dir, "paper_2", repeat=100)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="rebuild_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    first_client = FakeEmbeddingClient()
    rebuilder = _rebuilder(tmp_path, metadata_dir, backend, first_client)

    canary = rebuilder.run_canary()
    result = rebuilder.run_all()
    manifest = load_manifest(tmp_path / "rebuild_manifest.json")

    assert canary["completed_paper_count"] == 1
    assert result["status"] == "ready"
    assert result["paper_count"] == 2
    assert backend.count() == result["chunk_count"]
    assert {record["status"] for record in manifest["papers"].values()} == {"completed"}

    second_client = FakeEmbeddingClient()
    resumed_result = _rebuilder(
        tmp_path, metadata_dir, backend, second_client
    ).run_all()
    assert resumed_result["status"] == "ready"
    assert second_client.calls == 0

    third_client = FakeEmbeddingClient()
    ready_canary = _rebuilder(
        tmp_path, metadata_dir, backend, third_client
    ).run_canary()
    assert ready_canary["status"] == "ready"
    assert third_client.calls == 0


def test_partial_verify_returns_building_status_after_consistent_canary(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1", repeat=20)
    _write_parsed_fixture(metadata_dir, "paper_2", repeat=80)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="partial_verify_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    rebuilder = _rebuilder(tmp_path, metadata_dir, backend, FakeEmbeddingClient())
    rebuilder.run_canary()
    manifest_path = tmp_path / "rebuild_manifest.json"
    manifest_before = manifest_path.read_bytes()
    metadata_before = backend.metadata()

    result = rebuilder.verify(require_complete=False)

    assert result["status"] == "building"
    assert result["completed_paper_count"] == 1
    assert manifest_path.read_bytes() == manifest_before
    assert backend.metadata() == metadata_before
    validate_existing_chroma_store(str(tmp_path / "chroma"))


def test_verify_failure_does_not_create_absent_manifest_lock(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1")
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="read_lock_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    rebuilder = _rebuilder(
        tmp_path, metadata_dir, backend, FakeEmbeddingClient(), expected=1
    )
    manifest_path = tmp_path / "rebuild_manifest.json"
    write_manifest(
        manifest_path,
        create_build_manifest(metadata_dir=metadata_dir, contract=rebuilder.contract),
    )
    lock_path = tmp_path / ".rebuild_manifest.json.lock"

    with pytest.raises(FileNotFoundError, match="lock"):
        rebuilder.verify(require_complete=False)

    assert not lock_path.exists()


def test_partial_verify_rejects_completed_paper_dimension_mismatch(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1", repeat=20)
    _write_parsed_fixture(metadata_dir, "paper_2", repeat=80)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="partial_dimension_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    rebuilder = _rebuilder(tmp_path, metadata_dir, backend, FakeEmbeddingClient())
    rebuilder.run_canary()
    manifest_path = tmp_path / "rebuild_manifest.json"
    manifest = load_manifest(manifest_path)
    completed_record = next(iter(manifest["papers"].values()))
    completed_record["embedding_dimension"] = 999
    write_manifest(manifest_path, manifest)

    with pytest.raises(RuntimeError, match="dimension"):
        rebuilder.verify(require_complete=False)


@pytest.mark.parametrize(
    "metadata",
    [
        {"build_status": "building", "embedding_model": "wrong", "schema_version": 1},
        {"build_status": "building", "embedding_model": "bge-m3", "schema_version": 2},
    ],
)
def test_rebuilder_preflights_existing_collection_contract_before_manifest_or_upsert(
    tmp_path: Path, metadata: dict
):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1")
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="preflight_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata=metadata,
    )

    with pytest.raises(ValueError, match="collection metadata"):
        _rebuilder(tmp_path, metadata_dir, backend, FakeEmbeddingClient(), expected=1)

    assert backend.count() == 0
    assert not (tmp_path / "rebuild_manifest.json").exists()


def test_first_batch_locks_dimension_before_later_batch_mismatch(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1", repeat=100)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="dimension_lock_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )

    class MismatchedBatches(FakeEmbeddingClient):
        def embed_texts(self, texts):
            self.calls += 1
            dimension = 3 if self.calls == 1 else 2
            return [[1.0] * dimension for _ in texts]

    rebuilder = ChromaIndexRebuilder(
        metadata_dir=metadata_dir,
        manifest_path=tmp_path / "rebuild_manifest.json",
        backend=backend,
        embedding_client=MismatchedBatches(),
        batch_size=1,
        max_attempts=2,
        base_delay=0,
        git_head="test-head",
        chunk_settings={
            "strategy": "parent_child_sliding_window",
            "size": 100,
            "overlap": 10,
        },
        expected_source_count=1,
        sleep=lambda _: None,
    )

    with pytest.raises(ValueError, match="dimension"):
        rebuilder.run_all()

    assert backend.count() == 0
    assert backend.metadata()["embedding_dimension"] == 3
    assert backend.metadata()["build_status"] == "building"


@pytest.mark.parametrize("corruption", ["duplicate_source", "wrong_hash"])
def test_final_verify_requires_source_to_completed_paper_bijection(
    tmp_path: Path, corruption: str
):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1", repeat=25)
    _write_parsed_fixture(metadata_dir, "paper_2", repeat=45)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="bijection_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    rebuilder = _rebuilder(tmp_path, metadata_dir, backend, FakeEmbeddingClient())
    rebuilder.run_all()
    manifest_path = tmp_path / "rebuild_manifest.json"
    manifest = load_manifest(manifest_path)
    if corruption == "duplicate_source":
        manifest["papers"]["paper_2"]["source_path"] = manifest["papers"]["paper_1"][
            "source_path"
        ]
    else:
        manifest["papers"]["paper_2"]["sha256"] = "0" * 64
    write_manifest(manifest_path, manifest)

    with pytest.raises(RuntimeError, match="source"):
        rebuilder.verify(require_complete=True)


def test_verify_complete_requires_ready_collection_metadata(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1", repeat=30)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="readiness_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    rebuilder = _rebuilder(
        tmp_path, metadata_dir, backend, FakeEmbeddingClient(), expected=1
    )
    rebuilder.run_all()
    backend.update_build_metadata({"build_status": "failed"})

    with pytest.raises(RuntimeError, match="collection is not ready"):
        rebuilder.verify(require_complete=True)


def test_source_hash_change_replaces_only_changed_paper(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    changed = _write_parsed_fixture(metadata_dir, "paper_1", repeat=40)
    _write_parsed_fixture(metadata_dir, "paper_2", repeat=40)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="changed_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    _rebuilder(tmp_path, metadata_dir, backend, FakeEmbeddingClient()).run_all()
    paper_2_ids = backend.ids_for_paper("paper_2")
    _write_parsed_fixture(metadata_dir, "paper_1", repeat=120)

    _rebuilder(tmp_path, metadata_dir, backend, FakeEmbeddingClient()).run_all()

    assert backend.ids_for_paper("paper_2") == paper_2_ids
    manifest = load_manifest(tmp_path / "rebuild_manifest.json")
    changed_record = next(
        r for r in manifest["papers"].values() if r["source_path"] == changed.name
    )
    assert changed_record["sha256"] == source_sha256(changed)


def test_source_mutation_during_processing_is_not_marked_completed(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    source = _write_parsed_fixture(metadata_dir, "paper_1", repeat=40)
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="mutation_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )

    class MutatingClient(FakeEmbeddingClient):
        def embed_texts(self, texts):
            source.write_bytes(source.read_bytes() + b" ")
            return super().embed_texts(texts)

    with pytest.raises(RuntimeError, match="changed during processing"):
        _rebuilder(
            tmp_path, metadata_dir, backend, MutatingClient(), expected=1
        ).run_all()

    manifest = load_manifest(tmp_path / "rebuild_manifest.json")
    assert all(
        record["status"] != "completed" for record in manifest["papers"].values()
    )


@pytest.mark.parametrize(
    "relative",
    ["../outside_parsed.json", "/absolute_parsed.json", "C:/escape_parsed.json"],
)
def test_manifest_source_paths_must_stay_beneath_metadata_dir(
    tmp_path: Path, relative: str
):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    source = _write_parsed_fixture(metadata_dir, "paper_1")
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="path_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    rebuilder = _rebuilder(
        tmp_path, metadata_dir, backend, FakeEmbeddingClient(), expected=1
    )
    rebuilder.run_canary()
    manifest = load_manifest(tmp_path / "rebuild_manifest.json")
    manifest["sources"][0]["path"] = relative
    write_manifest(tmp_path / "rebuild_manifest.json", manifest)

    with pytest.raises(ValueError, match="source path"):
        rebuilder.verify(require_complete=False)

    assert source.exists()


def test_locked_manifest_updates_do_not_lose_concurrent_writers(tmp_path: Path):
    path = tmp_path / "manifest.json"
    write_manifest(path, {"counter": 0})

    def increment():
        for _ in range(10):
            update_manifest_locked(
                path, lambda data: {**data, "counter": data["counter"] + 1}
            )

    threads = [threading.Thread(target=increment) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert load_manifest(path) == {"counter": 40}


def test_manifest_read_lock_does_not_create_missing_lock_file(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, {"status": "building"})
    lock_path = tmp_path / ".manifest.json.lock"

    with pytest.raises(FileNotFoundError, match="lock"):
        with manifest_read_lock(manifest_path):
            pass

    assert not lock_path.exists()


def test_manifest_read_lock_synchronizes_with_existing_write_lock(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, {"status": "building"})
    with manifest_write_lock(manifest_path):
        pass
    entered = threading.Event()
    release = threading.Event()

    def hold_write_lock():
        with manifest_write_lock(manifest_path):
            entered.set()
            release.wait(timeout=2)

    thread = threading.Thread(target=hold_write_lock)
    thread.start()
    assert entered.wait(timeout=2)
    try:
        with pytest.raises(TimeoutError, match="locking rebuild manifest"):
            with manifest_read_lock(manifest_path, timeout=0.01):
                pass
    finally:
        release.set()
        thread.join(timeout=2)

    assert not thread.is_alive()


def test_manifest_replace_retries_windows_sharing_violation(
    tmp_path: Path, monkeypatch
):
    path = tmp_path / "manifest.json"
    calls = 0
    real_replace = __import__("os").replace

    def flaky_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls < 3:
            error = PermissionError("sharing violation")
            error.winerror = 32
            raise error
        return real_replace(source, destination)

    monkeypatch.setattr("app.services.chroma_rebuild.os.replace", flaky_replace)
    write_manifest(
        path,
        {"status": "new"},
        replace_attempts=3,
        replace_delay=0,
        sleep=lambda _: None,
    )

    assert calls == 3
    assert load_manifest(path) == {"status": "new"}


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"batch_size": True}, "batch_size"),
        ({"max_attempts": 0}, "max_attempts"),
        ({"expected_source_count": -1}, "expected_source_count"),
        ({"base_delay": float("nan")}, "base_delay"),
    ],
)
def test_rebuilder_rejects_invalid_constructor_arguments(tmp_path: Path, kwargs, match):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()

    class Backend:
        collection_name = "collection"

        def backend_name(self):
            return "chroma"

    arguments = dict(
        metadata_dir=metadata_dir,
        manifest_path=tmp_path / "manifest.json",
        backend=Backend(),
        embedding_client=FakeEmbeddingClient(),
        batch_size=2,
        max_attempts=3,
        base_delay=0.1,
        git_head="head",
        chunk_settings={"size": 500},
        expected_source_count=1,
    )
    arguments.update(kwargs)
    with pytest.raises(ValueError, match=match):
        ChromaIndexRebuilder(**arguments)
