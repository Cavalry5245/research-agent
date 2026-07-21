from fastapi.testclient import TestClient
import pytest

from app.main import app


class StubVectorStore:
    def backend_name(self):
        return "json"

    def metadata(self):
        return {"backend": "json", "chunk_count": 0}

    def count(self):
        return 0


def test_health_endpoint_reports_runtime_checks(monkeypatch, tmp_path):
    client = TestClient(app)
    monkeypatch.setattr(
        "app.main._resolve_upload_dir", lambda: str(tmp_path / "papers")
    )
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr(
        "app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata")
    )
    monkeypatch.setattr("app.main._get_vector_store", lambda: StubVectorStore())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["storage_writable"] is True
    assert body["vector_store_available"] is True
    assert "llm_configured" in body["config"]


def test_health_endpoint_reports_degraded_when_vector_store_unavailable(
    monkeypatch, tmp_path
):
    client = TestClient(app)
    monkeypatch.setattr(
        "app.main._resolve_upload_dir", lambda: str(tmp_path / "papers")
    )
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr(
        "app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata")
    )

    def fail_vector_store():
        raise RuntimeError("vector unavailable")

    monkeypatch.setattr("app.main._get_vector_store", fail_vector_store)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["vector_store_available"] is False


def test_health_endpoint_reports_building_chroma_as_degraded(monkeypatch, tmp_path):
    class BuildingChromaStore:
        def backend_name(self):
            return "chroma"

        def metadata(self):
            return {
                "backend": "chroma",
                "collection_name": "research_papers_bge_m3_v1",
                "build_status": "building",
                "embedding_dimension": 1024,
                "embedding_model": "bge-m3",
                "schema_version": 1,
                "embedding_provider": "api",
                "chunk_strategy": "parent_child_sliding_window",
                "chunk_size": 500,
                "chunk_overlap": 100,
                "source_count": 53,
                "build_git_head": "abc123",
            }

        def count(self):
            return 100

    client = TestClient(app)
    monkeypatch.setattr(
        "app.main._resolve_upload_dir", lambda: str(tmp_path / "papers")
    )
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr(
        "app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata")
    )
    monkeypatch.setattr("app.main._get_vector_store", lambda: BuildingChromaStore())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["vector_store_available"] is False


def test_health_endpoint_reports_ready_chroma_as_available(monkeypatch, tmp_path):
    class ReadyChromaStore:
        def backend_name(self):
            return "chroma"

        def metadata(self):
            return {
                "backend": "chroma",
                "collection_name": "research_papers_bge_m3_v1",
                "build_status": "ready",
                "embedding_dimension": 1024,
                "embedding_model": "bge-m3",
                "schema_version": 1,
                "embedding_provider": "api",
                "chunk_strategy": "parent_child_sliding_window",
                "chunk_size": 500,
                "chunk_overlap": 100,
                "source_count": 53,
                "build_git_head": "abc123",
            }

        def count(self):
            return 100

    client = TestClient(app)
    monkeypatch.setattr("app.main.settings.embedding_model", "bge-m3")
    monkeypatch.setattr(
        "app.main.settings.chroma_collection_name", "research_papers_bge_m3_v1"
    )
    monkeypatch.setattr(
        "app.main._resolve_upload_dir", lambda: str(tmp_path / "papers")
    )
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr(
        "app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata")
    )
    monkeypatch.setattr("app.main._get_vector_store", lambda: ReadyChromaStore())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["vector_store_available"] is True


@pytest.mark.parametrize(
    "metadata",
    [
        {
            "backend": "chroma",
            "collection_name": "research_papers_bge_m3_v1",
            "build_status": "failed",
            "embedding_dimension": 1024,
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
        {
            "backend": "chroma",
            "collection_name": "research_papers_bge_m3_v1",
            "build_status": "ready",
            "embedding_dimension": 0,
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
        {},
    ],
    ids=["failed", "invalid-dimension", "missing-backend"],
)
def test_health_endpoint_rejects_unusable_vector_metadata(
    monkeypatch, tmp_path, metadata
):
    class UnusableStore:
        def backend_name(self):
            return metadata.get("backend")

        def metadata(self):
            return metadata

        def count(self):
            return 1

    client = TestClient(app)
    monkeypatch.setattr(
        "app.main._resolve_upload_dir", lambda: str(tmp_path / "papers")
    )
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr(
        "app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata")
    )
    monkeypatch.setattr("app.main._get_vector_store", lambda: UnusableStore())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["vector_store_available"] is False


def test_health_endpoint_rejects_json_backend_with_failed_load(monkeypatch, tmp_path):
    class FailedJsonStore:
        def backend_name(self):
            return "json"

        def metadata(self):
            return {"backend": "json", "load_failed": True, "degraded": True}

        def count(self):
            return 0

    client = TestClient(app)
    monkeypatch.setattr(
        "app.main._resolve_upload_dir", lambda: str(tmp_path / "papers")
    )
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr(
        "app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata")
    )
    monkeypatch.setattr("app.main._get_vector_store", lambda: FailedJsonStore())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["vector_store_available"] is False
