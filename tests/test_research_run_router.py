from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.research_runs import router as research_runs_router
from app.research_workflow.paper_processing import PaperProcessingResult
from app.research_workflow.schemas import ResearchRunPaperItem
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore

app = FastAPI()
app.include_router(research_runs_router)


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


def test_research_run_execute_local_route(tmp_path, monkeypatch):
    service = _override_research_run_service(tmp_path, monkeypatch)

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="item-1",
                    title="Injected Paper",
                    zotero_item_id="ZOTERO1",
                    pdf_path=str(tmp_path / "paper.pdf"),
                    created_at=now,
                    updated_at=now,
                )
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            completed_at = datetime.now(timezone.utc)
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "fake-processor-paper",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": completed_at,
                        "completed_at": completed_at,
                    }
                ),
                chunk_count=3,
                note_path=str(tmp_path / "note.md"),
                vector_backend="fake",
            )

    try:
        client = TestClient(app)
        created = client.post(
            "/research-runs",
            json={"collection_id": "COLL123", "collection_name": "IRSTD"},
        ).json()

        from app.routers import research_runs as router

        app.dependency_overrides[router.get_collection_intake_service] = lambda: FakeIntake()
        app.dependency_overrides[router.get_paper_processing_service] = lambda: FakeProcessor()

        response = client.post(f"/research-runs/{created['run_id']}/execute-local")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["paper_items"][0]["paper_id"] == "fake-processor-paper"
        assert response.json()["paper_items"][0]["status"] == "completed"
    finally:
        app.dependency_overrides.clear()


def test_production_app_import_registers_research_run_routes():
    from app.main import app as production_app

    route_paths = {route.path for route in production_app.routes}

    assert "/research-runs" in route_paths
    assert "/research-runs/{run_id}/execute-local" in route_paths
