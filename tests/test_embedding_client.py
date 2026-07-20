import os
import sys
import logging
import types
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.embedding_client import EmbeddingClient


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


def fake_sentence_transformers_module(loader=FakeSentenceTransformer):
    fake_module = MagicMock()
    fake_module.SentenceTransformer = loader
    return fake_module


def test_embedding_client_rewrites_bge_short_name_to_baaai_repo():
    fake_module = MagicMock()
    fake_module.SentenceTransformer = FakeSentenceTransformer
    with patch(
        "app.services.embedding_client._check_available", return_value=True
    ), patch.dict(sys.modules, {"sentence_transformers": fake_module}):
        client = EmbeddingClient(model_name="bge-small-zh-v1.5")
        client._ensure_model()
        assert client._model.model_name == "BAAI/bge-small-zh-v1.5"


def test_embedding_client_prefers_cuda_when_available_and_device_auto():
    with patch(
        "app.services.embedding_client._check_available", return_value=True
    ), patch(
        "app.services.embedding_client._resolve_device", return_value="cuda"
    ), patch.dict(
        sys.modules, {"sentence_transformers": fake_sentence_transformers_module()}
    ):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")
        client._ensure_model()
        assert client.device == "cuda"
        assert client._model.device == "cuda"


def test_embedding_client_preserves_full_repo_id():
    with patch(
        "app.services.embedding_client._check_available", return_value=True
    ), patch.dict(
        sys.modules, {"sentence_transformers": fake_sentence_transformers_module()}
    ):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")
        client._ensure_model()
        assert client._model.model_name == "BAAI/bge-small-zh-v1.5"


def test_embedding_client_retries_when_loader_client_was_closed():
    loader = ClosedModelLoader()
    with patch(
        "app.services.embedding_client._check_available", return_value=True
    ), patch.dict(
        sys.modules,
        {"sentence_transformers": fake_sentence_transformers_module(loader)},
    ):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")
        client._ensure_model()
        assert loader.calls == 2
        assert client._model.model_name == "BAAI/bge-small-zh-v1.5"


def test_embedding_client_rebuilds_model_when_encode_hits_closed_client_error():
    first_model = MagicMock()
    first_model.get_embedding_dimension.return_value = 3
    first_model.encode.side_effect = RuntimeError(
        "Cannot send a request, as the client has been closed."
    )
    second_model = FakeSentenceTransformer("BAAI/bge-small-zh-v1.5")

    loader = MagicMock(side_effect=[first_model, second_model])
    with patch(
        "app.services.embedding_client._check_available", return_value=True
    ), patch(
        "app.services.embedding_client.settings.embedding_provider", "local"
    ), patch.dict(
        sys.modules,
        {"sentence_transformers": fake_sentence_transformers_module(loader)},
    ):
        client = EmbeddingClient(model_name="BAAI/bge-small-zh-v1.5")

        vectors = client.embed_texts(["hello"])

        assert vectors == [[0.1, 0.2, 0.3]]


def test_embedding_client_wraps_model_lookup_error_with_clear_message():
    def raise_lookup_error(model_name: str, device: str | None = None):
        raise OSError("not a valid model identifier")

    with patch(
        "app.services.embedding_client._check_available", return_value=True
    ), patch.dict(
        sys.modules,
        {
            "sentence_transformers": fake_sentence_transformers_module(
                raise_lookup_error
            )
        },
    ):
        client = EmbeddingClient(model_name="missing-model")
        with pytest.raises(RuntimeError, match="Embedding 模型加载失败"):
            client._ensure_model()


def test_api_embedding_sends_exact_configured_bge_m3_wire_model():
    requested = []

    class Embeddings:
        def create(self, *, model, input):
            requested.append((model, input))
            item = type("Item", (), {"index": 0, "embedding": [1.0, 2.0]})()
            return type("Response", (), {"data": [item]})()

    client = EmbeddingClient(model_name="bge-m3", batch_size=8)
    client._provider = "api"
    client._api_client = type("Api", (), {"embeddings": Embeddings()})()

    assert client.embed_texts(["text"]) == [[1.0, 2.0]]
    assert requested == [("bge-m3", ["text"])]


@pytest.mark.parametrize(
    "indices",
    [
        [0],
        [0, 0],
        [0, 2],
        [False, 1],
        [None, 1],
    ],
)
def test_api_embedding_rejects_invalid_provider_batch_indices(indices):
    class Embeddings:
        def create(self, *, model, input):
            data = [
                type("Item", (), {"index": index, "embedding": [1.0, 2.0]})()
                for index in indices
            ]
            return type("Response", (), {"data": data})()

    client = EmbeddingClient(model_name="bge-m3", batch_size=8)
    client._provider = "api"
    client._api_client = type("Api", (), {"embeddings": Embeddings()})()

    with pytest.raises(ValueError, match="indices"):
        client.embed_texts(["first", "second"])


def test_api_embedding_orders_complete_provider_batch_by_index():
    class Embeddings:
        def create(self, *, model, input):
            first = type("Item", (), {"index": 1, "embedding": [2.0]})()
            second = type("Item", (), {"index": 0, "embedding": [1.0]})()
            return type("Response", (), {"data": [first, second]})()

    client = EmbeddingClient(model_name="bge-m3", batch_size=8)
    client._provider = "api"
    client._api_client = type("Api", (), {"embeddings": Embeddings()})()

    assert client.embed_texts(["first", "second"]) == [[1.0], [2.0]]


def test_api_client_setup_logs_only_endpoint_and_key_presence(monkeypatch, caplog):
    constructed = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            constructed.append(kwargs)

    monkeypatch.setattr(
        "app.services.embedding_client.settings.embedding_base_url",
        "https://synthetic.invalid/v1",
    )
    monkeypatch.setattr(
        "app.services.embedding_client.settings.embedding_api_key",
        "sk-synthetic-never-log",
    )
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    client = EmbeddingClient(model_name="bge-m3")
    client._provider = "api"

    with caplog.at_level(logging.INFO, logger="app.services.embedding_client"):
        client._ensure_api_client()

    assert constructed
    assert "https://synthetic.invalid/v1" not in caplog.text
    assert "sk-synthetic-never-log" not in caplog.text
    assert "base_url_configured=True" in caplog.text
