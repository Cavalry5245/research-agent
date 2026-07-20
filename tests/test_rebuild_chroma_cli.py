from types import SimpleNamespace

import pytest

import scripts.rebuild_chroma_index as cli


class FakeBackend:
    collection_name = "research_papers_bge_m3_v1"

    def __init__(self, **kwargs):
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
        return {"paper_count": 53, "chunk_count": 100}

    def run_canary(self):
        self.calls.append(("canary",))
        return {"completed_paper_count": 1}

    def run_all(self):
        self.calls.append(("full",))
        return {"status": "ready", "paper_count": 53, "chunk_count": 100}


@pytest.fixture
def fake_cli(monkeypatch, tmp_path):
    FakeRebuilder.calls = []
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
    [("--verify-only", ("verify", True)), ("--canary-only", ("canary",))],
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


def test_cli_default_runs_canary_then_full(fake_cli):
    assert cli.main([]) == 0
    assert FakeRebuilder.calls == [("canary",), ("full",)]


def test_cli_returns_nonzero_when_requested_terminal_state_is_not_reached(
    fake_cli, monkeypatch
):
    monkeypatch.setattr(
        FakeRebuilder,
        "run_all",
        lambda self: {"status": "building", "paper_count": 52},
    )

    assert cli.main([]) == 1
