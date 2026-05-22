import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.embedding_client import EmbeddingClient, _resolve_model_name


def test_resolve_known_aliases():
    assert _resolve_model_name("bge-small-zh-v1.5") == "BAAI/bge-small-zh-v1.5"
    assert _resolve_model_name("bge-large-zh-v1.5") == "BAAI/bge-large-zh-v1.5"
    assert _resolve_model_name("m3e-base") == "moka-ai/m3e-base"


def test_resolve_unknown_passes_through():
    assert _resolve_model_name("some/custom-model") == "some/custom-model"


def test_client_init_keeps_model_name_and_lazy_loads():
    client = EmbeddingClient(model_name="bge-small-zh-v1.5")
    assert client.model_name == "bge-small-zh-v1.5"
    assert client._resolved_model_name == "BAAI/bge-small-zh-v1.5"
    assert client._model is None


def test_client_init_supports_m3e_alias():
    client = EmbeddingClient(model_name="m3e-base")
    assert client._resolved_model_name == "moka-ai/m3e-base"
