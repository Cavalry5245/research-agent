from types import SimpleNamespace
from pathlib import Path

import pytest

import scripts.rebuild_chroma_index as cli
from app.services.chroma_rebuild import (
    build_contract,
    create_build_manifest,
    preflight_rebuild as real_preflight_rebuild,
    write_manifest,
)
from app.services.vector_backends.chroma_backend import (
    validate_existing_chroma_store as real_validate_existing_chroma_store,
)


class FakeBackend:
    collection_name = "research_papers_bge_m3_v1"
    created = []

    def __init__(self, **kwargs):
        self.created.append(kwargs)
        self.collection_name = kwargs["collection_name"]

    def backend_name(self):
        return "chroma"


class FakeEmbeddingClient:
    provider = "api"
    model_name = "bge-m3"

    def __init__(self, **_kwargs):
        pass


class FakeRebuilder:
    calls = []

    def __init__(self, **_kwargs):
        pass

    def verify(self, *, require_complete=True):
        self.calls.append(("verify", require_complete))
        return {
            "status": "building",
            "completed_paper_count": 1,
            "paper_count": 1,
            "chunk_count": 2,
        }

    def run_canary(self):
        self.calls.append(("canary",))
        return {"completed_paper_count": 1}

    def run_all(self):
        self.calls.append(("full",))
        return {"status": "ready", "paper_count": 53, "chunk_count": 100}


@pytest.fixture
def fake_cli(monkeypatch, tmp_path):
    FakeRebuilder.calls = []
    FakeBackend.created = []
    settings = SimpleNamespace(
        metadata_dir=str(tmp_path / "metadata"),
        chroma_persist_dir=str(tmp_path / "chroma"),
        chroma_collection_name="research_papers_bge_m3_v1",
        embedding_batch_size=8,
        embedding_provider="api",
        embedding_model="bge-m3",
        embedding_base_url="https://synthetic.invalid/v1",
        embedding_api_key="sk-synthetic-never-print",
        child_chunk_size=500,
        child_chunk_overlap=100,
        chunk_strategy="parent_child_sliding_window",
    )
    monkeypatch.setattr(cli, "settings", settings)
    monkeypatch.setattr(cli, "ChromaVectorBackend", FakeBackend)
    monkeypatch.setattr(cli, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(cli, "ChromaIndexRebuilder", FakeRebuilder)
    monkeypatch.setattr(cli, "git_head", lambda: "abc123")
    monkeypatch.setattr(
        cli,
        "preflight_rebuild",
        lambda **kwargs: ([], {} if kwargs.get("require_manifest") else None),
    )
    monkeypatch.setattr(cli, "validate_existing_chroma_store", lambda _path: None)
    return settings


@pytest.mark.parametrize(
    "provider,model",
    [("local", "bge-m3"), ("api", "BAAI/bge-m3"), ("api", "m3e-base")],
)
def test_cli_rejects_non_api_or_non_exact_bge_m3(fake_cli, provider, model, capsys):
    fake_cli.embedding_provider = provider
    fake_cli.embedding_model = model

    assert cli.main([]) == 2
    assert (
        "requires EMBEDDING_PROVIDER=api and EMBEDDING_MODEL=bge-m3"
        in capsys.readouterr().err
    )


@pytest.mark.parametrize(
    "flag,expected_call",
    [("--verify-only", ("verify", False)), ("--canary-only", ("canary",))],
)
def test_cli_modes_print_only_configuration_presence(
    fake_cli, flag, expected_call, capsys
):
    assert cli.main([flag]) == 0

    captured = capsys.readouterr()
    assert expected_call in FakeRebuilder.calls
    assert "embedding_base_url_configured=True" in captured.out
    assert "embedding_api_key_configured=True" in captured.out
    assert fake_cli.embedding_base_url not in captured.out
    assert fake_cli.embedding_api_key not in captured.out
    if flag == "--verify-only":
        assert FakeBackend.created[0]["create_if_missing"] is False


@pytest.mark.parametrize("missing_field", ["embedding_base_url", "embedding_api_key"])
def test_cli_build_rejects_missing_api_configuration_before_opening_backend(
    fake_cli, missing_field, monkeypatch, capsys
):
    setattr(fake_cli, missing_field, "")
    monkeypatch.setattr(
        cli,
        "ChromaVectorBackend",
        lambda **_kwargs: pytest.fail("backend must not be opened"),
    )

    assert cli.main(["--canary-only"]) == 2
    captured = capsys.readouterr()
    assert "requires nonempty EMBEDDING_BASE_URL and EMBEDDING_API_KEY" in captured.err
    assert "embedding_base_url_configured=" in captured.out
    assert "embedding_api_key_configured=" in captured.out


def test_cli_verify_allows_missing_credentials_and_does_not_create_embedding_client(
    fake_cli, monkeypatch
):
    fake_cli.embedding_base_url = ""
    fake_cli.embedding_api_key = ""
    monkeypatch.setattr(
        cli,
        "EmbeddingClient",
        lambda **_kwargs: pytest.fail("verify-only must not create embedding client"),
    )

    assert cli.main(["--verify-only"]) == 0


def test_cli_default_runs_canary_then_full(fake_cli):
    assert cli.main([]) == 0
    assert FakeRebuilder.calls == [("canary",), ("full",)]
    assert FakeBackend.created[0]["initial_metadata"] == {
        "build_status": "building",
        "embedding_model": "bge-m3",
        "schema_version": 1,
    }
    assert FakeBackend.created[0]["create_if_missing"] is True


def test_cli_default_existing_manifest_runs_full_directly(fake_cli, monkeypatch):
    monkeypatch.setattr(
        cli, "preflight_rebuild", lambda **_kwargs: ([], {"status": "failed"})
    )

    assert cli.main([]) == 0
    assert FakeRebuilder.calls == [("full",)]


def test_cli_default_rerun_skips_canary_after_prior_full_failure(fake_cli, monkeypatch):
    manifests = iter([None, {"status": "failed"}])
    monkeypatch.setattr(
        cli, "preflight_rebuild", lambda **_kwargs: ([], next(manifests))
    )

    class FailOnceRebuilder(FakeRebuilder):
        full_attempts = 0

        def run_all(self):
            self.calls.append(("full",))
            type(self).full_attempts += 1
            if type(self).full_attempts == 1:
                raise RuntimeError("second source failed")
            return {"status": "ready", "paper_count": 53, "chunk_count": 100}

    monkeypatch.setattr(cli, "ChromaIndexRebuilder", FailOnceRebuilder)

    assert cli.main([]) == 1
    assert cli.main([]) == 0
    assert FakeRebuilder.calls == [("canary",), ("full",), ("full",)]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--collection", ""],
        ["--expected-source-count", "0"],
        ["--batch-size", "0"],
        ["--max-attempts", "-1"],
        ["--base-delay", "nan"],
        ["--max-delay", "-1"],
    ],
)
def test_cli_rejects_invalid_scalar_arguments_before_preflight_or_backend(
    fake_cli, monkeypatch, arguments
):
    monkeypatch.setattr(
        cli,
        "preflight_rebuild",
        lambda **_kwargs: pytest.fail("preflight must not run"),
    )
    monkeypatch.setattr(
        cli,
        "ChromaVectorBackend",
        lambda **_kwargs: pytest.fail("backend must not be opened"),
    )

    assert cli.main(arguments) == 2


def test_cli_verify_rejects_empty_building_state(fake_cli, monkeypatch):
    monkeypatch.setattr(
        FakeRebuilder,
        "verify",
        lambda self, require_complete=False: {
            "status": "building",
            "completed_paper_count": 0,
            "paper_count": 0,
            "chunk_count": 0,
        },
    )

    assert cli.main(["--verify-only"]) == 1


def test_cli_verify_rejects_incomplete_ready_state(fake_cli, monkeypatch):
    monkeypatch.setattr(
        FakeRebuilder,
        "verify",
        lambda self, require_complete=False: {
            "status": "ready",
            "completed_paper_count": 52,
            "paper_count": 52,
            "chunk_count": 100,
        },
    )

    assert cli.main(["--verify-only"]) == 1


@pytest.mark.parametrize("arguments", [["--verify-only"], ["--canary-only"], []])
def test_cli_preflight_failure_happens_before_backend_instantiation(
    fake_cli, monkeypatch, arguments
):
    monkeypatch.setattr(
        cli,
        "preflight_rebuild",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("preflight rejected")),
    )
    monkeypatch.setattr(
        cli,
        "ChromaVectorBackend",
        lambda **_kwargs: pytest.fail("backend must not be opened or created"),
    )

    assert cli.main(arguments) == 1


def test_cli_verify_missing_collection_opens_without_creation(fake_cli, monkeypatch):
    opened = []

    def missing_collection(**kwargs):
        opened.append(kwargs)
        raise RuntimeError("collection does not exist")

    monkeypatch.setattr(cli, "ChromaVectorBackend", missing_collection)

    assert cli.main(["--verify-only"]) == 1
    assert opened[0]["create_if_missing"] is False
    assert opened[0]["initial_metadata"] is None


def test_cli_invalid_source_count_creates_no_backend_or_manifest_artifacts(
    fake_cli, monkeypatch
):
    metadata_dir = Path(fake_cli.metadata_dir)
    metadata_dir.mkdir()
    persist_dir = Path(fake_cli.chroma_persist_dir)
    monkeypatch.setattr(cli, "preflight_rebuild", real_preflight_rebuild)
    monkeypatch.setattr(
        cli,
        "ChromaVectorBackend",
        lambda **_kwargs: pytest.fail("backend must not be created"),
    )

    assert cli.main(["--expected-source-count", "1"]) == 1
    assert not persist_dir.exists()
    assert not (
        persist_dir / "research_papers_bge_m3_v1.rebuild-manifest.json"
    ).exists()


def test_cli_verify_missing_manifest_keeps_persist_directory_absent(
    fake_cli, monkeypatch
):
    metadata_dir = Path(fake_cli.metadata_dir)
    metadata_dir.mkdir()
    (metadata_dir / "paper_parsed.json").write_text("{}", encoding="utf-8")
    persist_dir = Path(fake_cli.chroma_persist_dir)
    monkeypatch.setattr(cli, "preflight_rebuild", real_preflight_rebuild)
    monkeypatch.setattr(
        cli,
        "ChromaVectorBackend",
        lambda **_kwargs: pytest.fail("backend must not be opened"),
    )

    assert cli.main(["--verify-only", "--expected-source-count", "1"]) == 1
    assert not persist_dir.exists()


def test_cli_verify_missing_chroma_database_is_read_only_before_backend(
    fake_cli, monkeypatch
):
    metadata_dir = Path(fake_cli.metadata_dir)
    metadata_dir.mkdir()
    (metadata_dir / "paper_parsed.json").write_text("{}", encoding="utf-8")
    persist_dir = Path(fake_cli.chroma_persist_dir)
    persist_dir.mkdir()
    manifest_path = persist_dir / "research_papers_bge_m3_v1.rebuild-manifest.json"
    contract = build_contract(
        collection="research_papers_bge_m3_v1",
        provider="api",
        model="bge-m3",
        git_head="abc123",
        schema_version=1,
        chunk_settings={
            "strategy": "parent_child_sliding_window",
            "size": 500,
            "overlap": 100,
        },
    )
    write_manifest(
        manifest_path,
        create_build_manifest(metadata_dir=metadata_dir, contract=contract),
    )
    before = manifest_path.read_bytes()
    monkeypatch.setattr(cli, "preflight_rebuild", real_preflight_rebuild)
    monkeypatch.setattr(
        cli, "validate_existing_chroma_store", real_validate_existing_chroma_store
    )
    monkeypatch.setattr(
        cli,
        "ChromaVectorBackend",
        lambda **_kwargs: pytest.fail("backend must not be opened"),
    )

    assert cli.main(["--verify-only", "--expected-source-count", "1"]) == 1
    assert manifest_path.read_bytes() == before
    assert not (persist_dir / "chroma.sqlite3").exists()
    assert not (persist_dir / f".{manifest_path.name}.lock").exists()


def test_cli_returns_nonzero_when_requested_terminal_state_is_not_reached(
    fake_cli, monkeypatch
):
    monkeypatch.setattr(
        FakeRebuilder,
        "run_all",
        lambda self: {"status": "building", "paper_count": 52},
    )

    assert cli.main([]) == 1
