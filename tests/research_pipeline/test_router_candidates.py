"""
Tests for Research Pipeline Router candidate visibility

Verifies that candidates are visible through FastAPI GET endpoints.
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_pipeline.schemas import (
    ResearchRunDetailResponse,
    PaperCandidate,
    ResearchStage,
    ResearchEvent,
)


def test_get_run_detail_endpoint_includes_candidates(tmp_path):
    """GET /research-pipeline/runs/{run_id} should include candidates in response."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def get_run_detail(self, run_id: str):
            return ResearchRunDetailResponse(
                run_id=run_id,
                question="Test question with candidates",
                normalized_question=None,
                source_mode="web_search",
                zotero_collection_key=None,
                status="completed",
                max_reader_papers=5,
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
                candidates=[
                    PaperCandidate(
                        paper_id="paper_1",
                        source="semantic_scholar",
                        title="Attention Is All You Need",
                        authors=["Vaswani", "Shazeer"],
                        year=2017,
                        semantic_scholar_id="ss_1",
                        citation_count=50000,
                    ),
                    PaperCandidate(
                        paper_id="paper_2",
                        source="arxiv",
                        title="BERT",
                        authors=["Devlin"],
                        year=2018,
                        arxiv_id="1810.04805",
                    ),
                ],
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
        assert data["question"] == "Test question with candidates"
        assert data["status"] == "completed"

        # Verify candidates are in response
        assert "candidates" in data
        assert len(data["candidates"]) == 2

        # Verify first candidate
        c1 = data["candidates"][0]
        assert c1["paper_id"] == "paper_1"
        assert c1["source"] == "semantic_scholar"
        assert c1["title"] == "Attention Is All You Need"
        assert c1["authors"] == ["Vaswani", "Shazeer"]
        assert c1["year"] == 2017
        assert c1["semantic_scholar_id"] == "ss_1"
        assert c1["citation_count"] == 50000

        # Verify second candidate
        c2 = data["candidates"][1]
        assert c2["paper_id"] == "paper_2"
        assert c2["source"] == "arxiv"
        assert c2["title"] == "BERT"
        assert c2["authors"] == ["Devlin"]
        assert c2["year"] == 2018
        assert c2["arxiv_id"] == "1810.04805"

    finally:
        app.dependency_overrides.clear()


def test_get_run_detail_endpoint_empty_candidates(tmp_path):
    """GET /research-pipeline/runs/{run_id} should handle empty candidates list."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module

    app = FastAPI()
    app.include_router(router)

    class FakeService:
        def __init__(self, db_path: str):
            self.db_path = db_path

        def get_run_detail(self, run_id: str):
            return ResearchRunDetailResponse(
                run_id=run_id,
                question="Test question no candidates",
                normalized_question=None,
                source_mode="web_search",
                zotero_collection_key=None,
                status="queued",
                max_reader_papers=5,
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

        # Verify candidates key exists and is empty
        assert "candidates" in data
        assert data["candidates"] == []

    finally:
        app.dependency_overrides.clear()
