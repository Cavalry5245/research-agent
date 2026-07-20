from unittest.mock import Mock, patch

import pytest

from app.config import Settings
from app.services.vector_store import VectorStore


def test_vector_store_settings_have_versioned_chroma_collection():
    configured = Settings(
        _env_file=None,
        vector_store="chroma",
        chroma_persist_dir="tmp/chroma",
        chroma_collection_name="research_papers_bge_m3_v1",
    )
    assert configured.vector_store == "chroma"
    assert configured.chroma_persist_dir == "tmp/chroma"
    assert configured.chroma_collection_name == "research_papers_bge_m3_v1"


def test_vector_store_settings_have_chroma_defaults(monkeypatch):
    for key in (
        "VECTOR_STORE",
        "CHROMA_PERSIST_DIR",
        "CHROMA_COLLECTION_NAME",
        "CHROMA_REQUIRE_READY",
    ):
        monkeypatch.delenv(key, raising=False)

    configured = Settings(_env_file=None)

    assert configured.vector_store == "chroma"
    assert configured.chroma_persist_dir == "app/storage/vector_db"
    assert configured.chroma_collection_name == "research_papers_bge_m3_v1"
    assert configured.chroma_require_ready is True


def test_vector_store_uses_explicit_backend_instance(tmp_path):
    backend = Mock()
    backend.backend_name.return_value = "stub"

    store = VectorStore(persist_dir=str(tmp_path), backend=backend)

    assert store.backend_name() == "stub"


def test_vector_store_rejects_unknown_configured_backend(tmp_path):
    with patch("app.services.vector_store.settings.vector_store", "unknown"):
        with pytest.raises(ValueError, match="Unsupported vector store backend"):
            VectorStore(persist_dir=str(tmp_path))


def test_vector_store_selects_json_from_configuration(tmp_path):
    with patch("app.services.vector_store.settings.vector_store", "json"):
        store = VectorStore(persist_dir=str(tmp_path))

    assert store.backend_name() == "json"


def test_vector_store_forwards_chroma_open_settings(tmp_path):
    backend = Mock()
    with (
        patch("app.services.vector_store.settings.vector_store", "chroma"),
        patch(
            "app.services.vector_store.settings.chroma_collection_name",
            "configured_collection",
        ),
        patch("app.services.vector_store.settings.chroma_require_ready", True),
        patch(
            "app.services.vector_backends.chroma_backend.ChromaVectorBackend",
            return_value=backend,
        ) as chroma_backend,
    ):
        VectorStore(persist_dir=str(tmp_path))

    chroma_backend.assert_called_once_with(
        persist_dir=str(tmp_path),
        collection_name="configured_collection",
        require_ready=True,
    )
