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
from app.research_pipeline.runner import create_default_agent, PipelineRunner
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


def test_default_planner_stage_executes_and_persists_initial_plan(tmp_path):
    """
    Gate test: Default runner's planner stage executes and persists initial plan.

    Verifies that PipelineRunner with default agent factory can actually execute
    planner stage (not just having the method), and that initial plan is saved to store.
    """
    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    # Create run
    run_id = store.create_run(
        db_path=db_path,
        question="What are the latest advances in neural architecture search?",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Create runner with default agent factory
    runner = PipelineRunner(
        db_path=db_path,
        agent_factory=create_default_agent,
    )

    # Execute planner stage
    result = runner._execute_stage(run_id, "planner")

    # Should complete or degrade (not fail)
    assert result is not None
    assert "stage_status" in result
    assert result["stage_status"] in ["completed", "degraded"], \
        f"Planner stage should complete or degrade, got: {result['stage_status']}"

    # Verify stage status in store
    run_detail = store.get_run_detail(db_path, run_id)
    planner_stage = next((s for s in run_detail["stages"] if s["stage"] == "planner"), None)
    assert planner_stage is not None, "Planner stage should exist in store"
    assert planner_stage["status"] in ["completed", "degraded"], \
        f"Planner stage status should be completed/degraded, got: {planner_stage['status']}"

    # Verify initial plan was persisted
    plans = store.get_plans_by_run(db_path, run_id)
    assert len(plans) >= 1, "Should have at least one plan"

    initial_plan = next((p for p in plans if p["phase"] == "initial"), None)
    assert initial_plan is not None, "Should have initial plan"

    # Verify plan_data structure (LLM or fallback)
    plan_data = initial_plan["plan_data"]
    assert "queries" in plan_data, "Plan should have queries"
    assert isinstance(plan_data["queries"], list), "Queries should be a list"
    assert len(plan_data["queries"]) > 0, "Should have at least one query"

    assert "normalized_question" in plan_data, "Plan should have normalized_question"
    assert "fallback_used" in plan_data, "Plan should indicate if fallback was used"

    # Fallback is acceptable (no real LLM required)
    if plan_data["fallback_used"]:
        # Fallback should use original question as query
        assert plan_data["queries"][0] != "", "Fallback query should not be empty"
    else:
        # LLM success should have structured output
        assert "subquestions" in plan_data, "LLM plan should have subquestions"
        assert "relevance_criteria" in plan_data, "LLM plan should have relevance_criteria"


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
