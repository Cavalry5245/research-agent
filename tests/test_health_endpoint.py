from fastapi.testclient import TestClient

from app.main import app


class StubVectorStore:
    def metadata(self):
        return {"backend": "stub"}


def test_health_endpoint_reports_runtime_checks(monkeypatch, tmp_path):
    client = TestClient(app)
    monkeypatch.setattr("app.main._resolve_upload_dir", lambda: str(tmp_path / "papers"))
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr("app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata"))
    monkeypatch.setattr("app.main._get_vector_store", lambda: StubVectorStore())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["storage_writable"] is True
    assert body["vector_store_available"] is True
    assert "llm_configured" in body["config"]


def test_health_endpoint_reports_degraded_when_vector_store_unavailable(monkeypatch, tmp_path):
    client = TestClient(app)
    monkeypatch.setattr("app.main._resolve_upload_dir", lambda: str(tmp_path / "papers"))
    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path / "notes"))
    monkeypatch.setattr("app.main._resolve_metadata_dir", lambda: str(tmp_path / "metadata"))

    def fail_vector_store():
        raise RuntimeError("vector unavailable")

    monkeypatch.setattr("app.main._get_vector_store", fail_vector_store)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["vector_store_available"] is False
