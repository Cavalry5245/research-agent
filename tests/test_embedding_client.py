import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.embedding_client import EmbeddingClient


class FakeSentenceTransformer:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def get_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts, show_progress_bar=False):
        return FakeArray([[0.1, 0.2, 0.3] for _ in texts])


class FakeArray(list):
    def tolist(self):
        return list(self)


class ClosedModelLoader:
    def __init__(self):
        self.calls = 0

    def __call__(self, model_name: str):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Cannot send a request, as the client has been closed.")
        return FakeSentenceTransformer(model_name)


def test_embedding_client_rewrites_bge_short_name_to_baaai_repo():
    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "sentence_transformers.SentenceTransformer", FakeSentenceTransformer
    ):
        client = EmbeddingClient(model_name="bge-small-zh-v1.5")
        client._ensure_model()
        assert client._model.model_name == "BAAI/bge-small-zh-v1.5"


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


def test_embedding_client_wraps_model_lookup_error_with_clear_message():
    def raise_lookup_error(model_name: str):
        raise OSError("not a valid model identifier")

    with patch("app.services.embedding_client._check_available", return_value=True), patch(
        "sentence_transformers.SentenceTransformer", side_effect=raise_lookup_error
    ):
        client = EmbeddingClient(model_name="missing-model")
        with pytest.raises(RuntimeError, match="Embedding 模型加载失败"):
            client._ensure_model()
