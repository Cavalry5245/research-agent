"""
Integration test for PlannerAgentWrapper execution via runner

Verifies that planner stage actually executes via PipelineRunner.
"""

import pytest
from app.research_pipeline import store
from app.research_pipeline.runner import PipelineRunner, create_default_agent


def test_planner_wrapper_executes_via_runner(tmp_path):
    """PlannerAgentWrapper should execute successfully via PipelineRunner._execute_stage()."""
    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    # Create run
    run_id = store.create_run(
        db_path=db_path,
        question="What are the latest advances in transformer models?",
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

    # Should complete successfully (no candidates yet, so only initial plan)
    assert result is not None
    assert "stage_status" in result
    assert result["stage_status"] == "completed"
    assert "initial_plan_version" in result
    assert result["candidates_available"] is False

    # Verify stage was marked completed
    run_detail = store.get_run_detail(db_path, run_id)
    planner_stage = next(s for s in run_detail["stages"] if s["stage"] == "planner")
    assert planner_stage["status"] == "completed"

    # Verify initial plan was saved
    plans = store.get_plans_by_run(db_path, run_id)
    assert len(plans) >= 1
    initial_plan = next(p for p in plans if p["phase"] == "initial")
    assert initial_plan is not None
    assert "queries" in initial_plan["plan_data"]


def test_planner_wrapper_executes_with_candidates(tmp_path):
    """PlannerAgentWrapper should execute candidate selection when candidates exist."""
    from app.research_pipeline.schemas import PaperCandidate

    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    # Create run
    run_id = store.create_run(
        db_path=db_path,
        question="Test question with candidates",
        source_mode="web_search",
        max_reader_papers=3,
        reader_concurrency=3,
    )

    # Add some candidates (simulating retriever completion)
    for i in range(5):
        candidate = PaperCandidate(
            paper_id=f"paper_{i}",
            source="semantic_scholar",
            title=f"Test Paper {i}",
            authors=["Author"],
            year=2023,
            citation_count=100 - i * 10,  # Descending order
        )
        store.create_candidate(db_path, run_id, candidate)

    # Create runner and execute planner
    runner = PipelineRunner(
        db_path=db_path,
        agent_factory=create_default_agent,
    )

    result = runner._execute_stage(run_id, "planner")

    # Should complete with candidate selection
    assert result["stage_status"] == "completed"
    assert result["candidates_available"] is True
    assert result["selected_count"] <= 3  # max_reader_papers
    assert "selection_plan_version" in result

    # Verify both plans saved
    plans = store.get_plans_by_run(db_path, run_id)
    assert len(plans) == 2
    phases = {p["phase"] for p in plans}
    assert "initial" in phases
    assert "candidate_selection" in phases


def test_runner_replans_after_retriever_before_reader(tmp_path):
    """PipelineRunner should create candidate_selection after retrieval before reader."""
    from app.research_pipeline.schemas import PaperCandidate
    from app.research_pipeline.runner import StubAgent

    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    run_id = store.create_run(
        db_path=db_path,
        question="Test question with post-retrieval planning",
        source_mode="web_search",
        max_reader_papers=3,
        reader_concurrency=3,
    )

    class FakeRetriever:
        def execute(self):
            for i in range(5):
                store.create_candidate(
                    db_path,
                    run_id,
                    PaperCandidate(
                        paper_id=f"paper_{i}",
                        source="arxiv",
                        title=f"Test Paper {i}",
                        authors=["Author"],
                        year=2024,
                    ),
                )
            return {"candidates_found": 5}

    class ReaderAssertsSelection:
        def execute(self):
            plans = store.get_plans_by_run(db_path, run_id)
            candidate_plans = [p for p in plans if p["phase"] == "candidate_selection"]
            assert candidate_plans, "reader should not run before candidate_selection exists"
            return {"papers_read": 0, "cards_created": 0}

    class FakePlanner:
        def execute(self):
            candidates = store.get_candidates(db_path, run_id)
            if not candidates:
                store.create_plan(
                    db_path,
                    run_id,
                    phase="initial",
                    plan_data={"normalized_question": "Test question", "queries": ["Test question"]},
                )
                return {"stage_status": "completed", "candidates_available": False}

            store.create_plan(
                db_path,
                run_id,
                phase="candidate_selection",
                plan_data={"selected_paper_ids": [c["paper_id"] for c in candidates[:3]]},
            )
            return {
                "stage_status": "completed",
                "candidates_available": True,
                "selected_count": 3,
            }

    def factory(stage: str, db_path_arg: str, run_id_arg: str):
        if stage == "planner":
            return FakePlanner()
        if stage == "retriever":
            return FakeRetriever()
        if stage == "reader":
            return ReaderAssertsSelection()
        return StubAgent(stage, db_path_arg, run_id_arg)

    runner = PipelineRunner(db_path=db_path, agent_factory=factory)

    runner.run(run_id)

    plans = store.get_plans_by_run(db_path, run_id)
    assert [p["phase"] for p in plans].count("candidate_selection") == 1


def test_planner_wrapper_skips_initial_plan_when_replanning(tmp_path, monkeypatch):
    """Second planner pass should reuse the existing initial plan."""
    from app.research_pipeline.agents.planner import PlannerAgent
    from app.research_pipeline.schemas import PaperCandidate

    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    run_id = store.create_run(
        db_path=db_path,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=3,
        reader_concurrency=3,
    )
    store.create_plan(
        db_path,
        run_id,
        phase="initial",
        plan_data={"normalized_question": "Test question", "queries": ["Test question"]},
    )
    for i in range(4):
        store.create_candidate(
            db_path,
            run_id,
            PaperCandidate(
                paper_id=f"paper_{i}",
                source="arxiv",
                title=f"Test Paper {i}",
                authors=["Author"],
                year=2024,
            ),
        )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("plan_initial should not be called during replanning")

    monkeypatch.setattr(PlannerAgent, "plan_initial", fail_if_called)

    runner = PipelineRunner(db_path=db_path, agent_factory=create_default_agent)
    result = runner._execute_stage(run_id, "planner")

    assert result["candidates_available"] is True
    assert result["selected_count"] <= 3
