import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk, PaperParseResult, Section
from app.services.chunker import chunk_paper
from app.services.embedding_client import EmbeddingClient
from app.services.paper_status import get_index_status
from app.services.vector_store import VectorStore


class FakeSentenceTransformer:
    def __init__(self, model_name: str, device: str | None = None):
        self.model_name = model_name
        self.device = device

    def get_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts, show_progress_bar=False, batch_size=None):
        return FakeArray([[0.1, 0.2, 0.3] for _ in texts])


class FakeArray(list):
    def tolist(self):
        return list(self)


class ClosedModelLoader:
    def __init__(self):
        self.calls = 0

    def __call__(self, model_name: str, device: str | None = None):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Cannot send a request, as the client has been closed.")
        return FakeSentenceTransformer(model_name, device=device)


def _make_chunk(paper_id: str, section: str, content: str, seq: int) -> Chunk:
    return Chunk(
        chunk_id=f"{paper_id}_chunk_{seq:04d}",
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        section=section,
        content=content,
    )


def _make_parsed_result(paper_id: str = "paper_A") -> PaperParseResult:
    return PaperParseResult(
        paper_id=paper_id,
        title="Paper A",
        abstract="Abstract",
        sections=[
            Section(heading="Method", content="A" * 1200),
            Section(heading="Experiment", content="B" * 900),
        ],
        full_text=("A" * 1200) + ("B" * 900),
    )


def test_embedding_client_rewrites_bge_short_name_to_baaai_repo():
    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "sentence_transformers.SentenceTransformer", FakeSentenceTransformer
    ):
        client = EmbeddingClient(model_name="bge-small-zh-v1.5")
        client._ensure_model()
        assert client._model.model_name == "BAAI/bge-small-zh-v1.5"


def test_embedding_client_prefers_cuda_when_available_and_device_auto():
    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "app.services.embedding_client._resolve_device", return_value="cuda"
    ), patch("sentence_transformers.SentenceTransformer", FakeSentenceTransformer):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")
        client._ensure_model()
        assert client.device == "cuda"
        assert client._model.device == "cuda"


def test_embedding_client_preserves_full_repo_id():
    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "sentence_transformers.SentenceTransformer", FakeSentenceTransformer
    ):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")
        client._ensure_model()
        assert client._model.model_name == "BAAI/bge-small-zh-v1.5"


def test_embedding_client_retries_when_loader_client_was_closed():
    loader = ClosedModelLoader()
    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "sentence_transformers.SentenceTransformer", side_effect=loader
    ):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")
        client._ensure_model()
        assert loader.calls == 2
        assert client._model.model_name == "BAAI/bge-small-zh-v1.5"


def test_embedding_client_rebuilds_model_when_encode_hits_closed_client_error():
    first_model = MagicMock()
    first_model.get_embedding_dimension.return_value = 3
    first_model.encode.side_effect = RuntimeError("Cannot send a request, as the client has been closed.")
    second_model = FakeSentenceTransformer("BAAI/bge-small-zh-v1.5")

    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "sentence_transformers.SentenceTransformer", side_effect=[first_model, second_model]
    ):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")

        vectors = client.embed_texts(["hello"])

        assert vectors == [[0.1, 0.2, 0.3]]


def test_embedding_client_wraps_model_lookup_error_with_clear_message():
    def raise_lookup_error(model_name: str, device: str | None = None):
        raise OSError("not a valid model identifier")

    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "sentence_transformers.SentenceTransformer", side_effect=raise_lookup_error
    ):
        client = EmbeddingClient(model_name="missing-model")
        with pytest.raises(RuntimeError, match="Embedding 模型加载失败"):
            client._ensure_model()


def test_vector_store_add_chunks_replaces_same_chunk_ids_instead_of_duplication():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunk = _make_chunk("paper_A", "Method", "one", 1)

        store.add_chunks([chunk], [[1.0, 0.0]])
        store.add_chunks([chunk], [[1.0, 0.0]])

        assert store.count() == 1


def test_get_index_status_reports_existing_chunks_for_paper():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk("paper_A", "Method", "one", 1),
            _make_chunk("paper_A", "Experiment", "two", 2),
        ]
        store.add_chunks(chunks, [[1.0, 0.0], [0.0, 1.0]])

        status = get_index_status(store, "paper_A")

        assert status["indexed"] is True
        assert status["chunk_count"] == 2


def test_chunk_paper_expected_volume_for_medium_document():
    parsed = _make_parsed_result()

    chunks = chunk_paper(parsed)

    assert len(chunks) >= 2
