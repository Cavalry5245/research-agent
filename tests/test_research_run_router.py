from fastapi.testclient import TestClient

from app.main import app
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore


class RejectDefaultService:
    def create_run(self, request):
        raise AssertionError("FastAPI dependency override was not used")

    def list_runs(self):
        raise AssertionError("FastAPI dependency override was not used")

    def get_run(self, run_id):
        raise AssertionError("FastAPI dependency override was not used")

    def cancel_run(self, run_id):
        raise AssertionError("FastAPI dependency override was not used")


def _override_research_run_service(tmp_path, monkeypatch) -> ResearchRunService:
    from app.routers import research_runs as router

    service = ResearchRunService(
        store=FileResearchRunStore(tmp_path / "runs.json"),
        vault_root=tmp_path / "vault",
    )
    monkeypatch.setattr(router, "_service_instance", RejectDefaultService())
    app.dependency_overrides[router.get_research_run_service] = lambda: service
    return service


def test_research_run_routes_create_list_get_and_cancel(tmp_path, monkeypatch):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        client = TestClient(app)

        create_response = client.post(
            "/research-runs",
            json={
                "collection_id": "COLL123",
                "collection_name": "IRSTD",
                "goal": "Create an IRSTD review",
                "options": {"max_papers": 3, "semantic_scholar": True},
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["collection_id"] == "COLL123"
        assert created["steps"][0]["agent"] == "CollectionIntakeAgent"

        list_response = client.get("/research-runs")
        assert list_response.status_code == 200
        assert list_response.json()["count"] == 1

        detail_response = client.get(f"/research-runs/{created['run_id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["run_id"] == created["run_id"]

        cancel_response = client.delete(f"/research-runs/{created['run_id']}")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "cancelled"

        conflict_response = client.delete(f"/research-runs/{created['run_id']}")
        assert conflict_response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_research_run_detail_missing_returns_404(tmp_path, monkeypatch):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        client = TestClient(app)
        response = client.get("/research-runs/missing")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
