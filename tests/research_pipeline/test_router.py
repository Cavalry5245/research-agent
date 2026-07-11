"""
Tests for Research Pipeline Router

Verifies FastAPI endpoints for research pipeline operations.
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_pipeline.schemas import (
    ResearchRunCreateRequest,
    ResearchRunCreateResponse,
    ResearchRunListResponse,
    ResearchRunDetailResponse,
)


def test_create_run_endpoint(tmp_path):
    """Test POST /research-pipeline/runs creates a new run."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    # Mock the service
    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path
            self.runs = {}

        def create_run(self, request, runner_scheduler=None):
            run_id = f"run_{len(self.runs) + 1}"
            self.runs[run_id] = {
                "run_id": run_id,
                "question": request.question,
                "status": "queued",
            }
            return ResearchRunCreateResponse(
                run_id=run_id,
                status="queued",
                created_at=datetime.utcnow(),
            )

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.post(
            "/research-pipeline/runs",
            json={
                "question": "What are the latest advances in IR detectors?",
                "source_mode": "hybrid",
                "max_reader_papers": 5,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["run_id"] == "run_1"
        assert data["status"] == "queued"
        assert "created_at" in data
    finally:
        app.dependency_overrides.clear()


def test_create_run_validation_error_returns_400(tmp_path):
    """Test POST /research-pipeline/runs with invalid data returns 400."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def create_run(self, request, runner_scheduler=None):
            raise ValueError("question cannot be empty")

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.post(
            "/research-pipeline/runs",
            json={
                "question": "",
                "source_mode": "hybrid",
            },
        )

        assert response.status_code == 400
        assert "question cannot be empty" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_list_runs_endpoint(tmp_path):
    """Test GET /research-pipeline/runs lists all runs."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def list_runs(self, limit=50):
            from app.research_pipeline.schemas import ResearchRunSummary
            return ResearchRunListResponse(
                count=2,
                runs=[
                    ResearchRunSummary(
                        run_id="run_1",
                        question="Test question 1",
                        source_mode="web_search",
                        status="completed",
                        error=None,
                        created_at=datetime.utcnow().isoformat(),
                    ),
                    ResearchRunSummary(
                        run_id="run_2",
                        question="Test question 2",
                        source_mode="hybrid",
                        status="running",
                        error=None,
                        created_at=datetime.utcnow().isoformat(),
                    ),
                ],
            )

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.get("/research-pipeline/runs")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["runs"]) == 2
        assert data["runs"][0]["run_id"] == "run_1"
        assert data["runs"][1]["run_id"] == "run_2"
    finally:
        app.dependency_overrides.clear()


def test_get_run_detail_endpoint(tmp_path):
    """Test GET /research-pipeline/runs/{run_id} returns run details."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def get_run_detail(self, run_id: str):
            if run_id != "run_1":
                raise ValueError(f"Run {run_id} not found")

            return ResearchRunDetailResponse(
                run_id="run_1",
                question="Test question",
                normalized_question=None,
                source_mode="hybrid",
                zotero_collection_key=None,
                status="completed",
                max_reader_papers=8,
                reader_concurrency=3,
                year_start=None,
                year_end=None,
                venue_filter=[],
                keywords=[],
                created_at=datetime.utcnow(),
                started_at=None,
                completed_at=None,
                failed_at=None,
                cancelled_at=None,
                error=None,
                stages=[],
                events=[],
                candidates=[],
                cards=[],
                plan=None,
                report=None,
            )

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.get("/research-pipeline/runs/run_1")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run_1"
        assert data["question"] == "Test question"
        assert data["status"] == "completed"
        assert data["stages"] == []
        assert data["events"] == []
    finally:
        app.dependency_overrides.clear()


def test_get_run_detail_not_found_returns_404(tmp_path):
    """Test GET /research-pipeline/runs/{run_id} with invalid ID returns 404."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def get_run_detail(self, run_id: str):
            raise ValueError(f"Run {run_id} not found")

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.get("/research-pipeline/runs/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cancel_run_endpoint(tmp_path):
    """Test POST /research-pipeline/runs/{run_id}/cancel cancels a run."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path
            self.cancelled = []

        def cancel_run(self, run_id: str):
            if run_id == "nonexistent":
                raise ValueError(f"Run {run_id} not found")
            self.cancelled.append(run_id)

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.post("/research-pipeline/runs/run_1/cancel")

        assert response.status_code == 200
        assert response.json()["message"] == "Run cancelled successfully"
        assert "run_1" in fake_service.cancelled
    finally:
        app.dependency_overrides.clear()


def test_cancel_run_not_found_returns_404(tmp_path):
    """Test POST /research-pipeline/runs/{run_id}/cancel with invalid ID returns 404."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def cancel_run(self, run_id: str):
            raise ValueError(f"Run {run_id} not found")

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.post("/research-pipeline/runs/nonexistent/cancel")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cancel_run_conflict_returns_409(tmp_path):
    """Test POST /research-pipeline/runs/{run_id}/cancel on completed run returns 409."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def cancel_run(self, run_id: str):
            raise ValueError("Cannot cancel run with status completed")

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.post("/research-pipeline/runs/run_1/cancel")

        assert response.status_code == 409
        assert "Cannot cancel" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_delete_run_endpoint(tmp_path):
    """Test DELETE /research-pipeline/runs/{run_id} deletes a run."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path
            self.deleted = []

        def delete_run(self, run_id: str):
            if run_id == "nonexistent":
                raise ValueError(f"Run {run_id} not found")
            self.deleted.append(run_id)

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.delete("/research-pipeline/runs/run_1")

        assert response.status_code == 204
        assert response.content == b""
        assert "run_1" in fake_service.deleted
    finally:
        app.dependency_overrides.clear()


def test_delete_run_not_found_returns_404(tmp_path):
    """Test DELETE /research-pipeline/runs/{run_id} with invalid ID returns 404."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def delete_run(self, run_id: str):
            raise ValueError(f"Run {run_id} not found")

    fake_service = FakeService(str(tmp_path / "test.db"))
    app.dependency_overrides[router_module.get_service] = lambda: fake_service

    try:
        client = TestClient(app)
        response = client.delete("/research-pipeline/runs/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_router_mounted_with_correct_prefix():
    """Test router uses /research-pipeline prefix."""
    from app.research_pipeline.router import router

    assert router.prefix == "/research-pipeline"
    assert "research-pipeline" in router.tags


def test_production_app_includes_research_pipeline_router():
    """Test main app includes research pipeline router."""
    from app.main import app

    route_paths = {getattr(route, "path", None) for route in app.routes}

    # Check that research pipeline routes are registered
    assert "/research-pipeline/runs" in route_paths
    assert "/research-pipeline/runs/{run_id}" in route_paths
    assert "/research-pipeline/runs/{run_id}/cancel" in route_paths
