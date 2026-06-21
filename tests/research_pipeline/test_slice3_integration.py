"""
Integration tests for Slice 3 API visibility

Verifies that PlannerAgentWrapper has execute() and PaperCards are visible via API.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_pipeline import store
from app.research_pipeline.runner import create_default_agent
from app.research_pipeline.schemas import PaperCandidate, PaperCard


def test_planner_wrapper_has_execute_method(tmp_path):
    """PlannerAgentWrapper created by create_default_agent should have execute() method."""
    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    run_id = store.create_run(
        db_path=db_path,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Create planner agent via factory
    planner_agent = create_default_agent("planner", db_path, run_id)

    # Should have execute() method
    assert hasattr(planner_agent, "execute"), "PlannerAgentWrapper must have execute() method"
    assert callable(planner_agent.execute), "execute() must be callable"


def test_service_returns_paper_cards_in_detail(tmp_path):
    """ResearchPipelineService.get_run_detail() should return PaperCards from store."""
    from app.research_pipeline.service import ResearchPipelineService

    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    # Create run
    run_id = store.create_run(
        db_path=db_path,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Add a candidate first (PaperCard requires existing candidate)
    candidate = PaperCandidate(
        paper_id="paper_1",
        source="semantic_scholar",
        title="Test Paper",
        authors=["Author1"],
        year=2023,
    )
    store.create_candidate(db_path, run_id, candidate)

    # Add a paper card
    card = PaperCard(
        paper_id="paper_1",
        status="completed",
        extraction_mode="abstract_only",
        title="Test Paper",
        research_problem="Test problem",
        method="Test method",
    )
    store.create_paper_card(db_path, run_id, card)

    # Get run detail through service
    service = ResearchPipelineService(db_path)
    detail = service.get_run_detail(run_id)

    # Should have 1 card
    assert len(detail.cards) == 1
    assert detail.cards[0].paper_id == "paper_1"
    assert detail.cards[0].title == "Test Paper"
    assert detail.cards[0].extraction_mode == "abstract_only"


def test_api_endpoint_returns_paper_cards(tmp_path):
    """GET /research-pipeline/runs/{run_id} should return PaperCards in response."""
    from app.research_pipeline.router import router
    from app.research_pipeline import router as router_module
    from app.research_pipeline.service import ResearchPipelineService

    app = FastAPI()
    app.include_router(router)

    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    # Create run with candidate and card
    run_id = store.create_run(
        db_path=db_path,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    candidate = PaperCandidate(
        paper_id="paper_api",
        source="arxiv",
        title="API Test Paper",
        authors=["API Author"],
        year=2024,
    )
    store.create_candidate(db_path, run_id, candidate)

    card = PaperCard(
        paper_id="paper_api",
        status="degraded",
        extraction_mode="pdf",
        title="API Test Paper",
        research_problem="API problem",
        error="LLM unavailable",
    )
    store.create_paper_card(db_path, run_id, card)

    # Override service dependency
    service = ResearchPipelineService(db_path)
    app.dependency_overrides[router_module.get_service] = lambda: service

    try:
        client = TestClient(app)
        response = client.get(f"/research-pipeline/runs/{run_id}")

        assert response.status_code == 200
        data = response.json()

        # Should have cards in response
        assert "cards" in data
        assert len(data["cards"]) == 1
        assert data["cards"][0]["paper_id"] == "paper_api"
        assert data["cards"][0]["title"] == "API Test Paper"
        assert data["cards"][0]["extraction_mode"] == "pdf"
        assert data["cards"][0]["status"] == "degraded"
        assert data["cards"][0]["error"] == "LLM unavailable"

    finally:
        app.dependency_overrides.clear()
