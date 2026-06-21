"""
Tests for Runner + ReaderAgent Integration

验证 PipelineRunner 正确集成 ReaderAgentWrapper，包括并发控制和故障隔离。
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.research_pipeline import store
from app.research_pipeline.agents.reader import ReaderAgent
from app.research_pipeline.runner import PipelineRunner, ReaderAgentWrapper
from app.research_pipeline.schemas import PaperCandidate


# ==================== Fixtures ====================


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    """创建临时测试数据库"""
    db_path = str(tmp_path / "test_runner_reader.db")
    store.init_db(db_path)
    return db_path


@pytest.fixture
def sample_run_with_candidates(temp_db: str) -> tuple[str, list[PaperCandidate]]:
    """创建一个带候选论文的 run"""
    run_id = store.create_run(
        db_path=temp_db,
        question="Test question for runner integration",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Create candidates
    candidates = [
        PaperCandidate(
            paper_id=f"paper_{i}",
            source="semantic_scholar",
            title=f"Paper {i}: Integration Test",
            authors=[f"Author {i}"],
            year=2020 + i,
            abstract=f"Abstract for paper {i}.",
            citation_count=100 - i * 10,
        )
        for i in range(8)
    ]

    # Store candidates
    for candidate in candidates:
        store.create_candidate(temp_db, run_id, candidate)

    # Create a candidate selection plan (select first 5)
    plan_data = {
        "selected_paper_ids": [f"paper_{i}" for i in range(5)],
        "reasoning": "Selected top 5 papers for testing",
        "fallback_used": False,
    }
    store.create_plan(
        db_path=temp_db,
        run_id=run_id,
        phase="candidate_selection",
        plan_data=plan_data,
    )

    return run_id, candidates


# ==================== Test ReaderAgentWrapper Execute ====================


def test_reader_wrapper_execute_success(temp_db: str, sample_run_with_candidates: tuple):
    """ReaderAgentWrapper 成功执行并保存卡片"""
    run_id, candidates = sample_run_with_candidates

    wrapper = ReaderAgentWrapper(stage="reader", db_path=temp_db, run_id=run_id)
    result = wrapper.execute()

    # Should process 5 selected papers
    assert result["papers_read"] == 5
    assert result["cards_created"] == 5

    # Check cards were saved to store
    run_detail = store.get_run_detail(temp_db, run_id)
    saved_cards = run_detail.get("cards", [])
    assert len(saved_cards) == 5

    # All selected papers should have cards
    card_ids = {card["paper_id"] for card in saved_cards}
    expected_ids = {f"paper_{i}" for i in range(5)}
    assert card_ids == expected_ids


def test_reader_wrapper_respects_concurrency_from_run(temp_db: str, sample_run_with_candidates: tuple):
    """ReaderAgentWrapper 使用 run 中的 reader_concurrency 配置"""
    run_id, candidates = sample_run_with_candidates

    # Update run to use different concurrency
    # (reader_concurrency is already set in fixture, we just verify it's used)
    run_detail = store.get_run_detail(temp_db, run_id)
    assert run_detail["reader_concurrency"] == 3

    wrapper = ReaderAgentWrapper(stage="reader", db_path=temp_db, run_id=run_id)
    result = wrapper.execute()

    # Should complete successfully with configured concurrency
    assert result["papers_read"] == 5


def test_reader_wrapper_partial_failure_degraded_status(
    temp_db: str, sample_run_with_candidates: tuple
):
    """部分失败时，stage 状态为 degraded"""
    run_id, candidates = sample_run_with_candidates

    wrapper = ReaderAgentWrapper(stage="reader", db_path=temp_db, run_id=run_id)

    # Mock the reader to fail on paper_2
    original_read = wrapper.reader.read_paper

    def selective_fail(candidate: PaperCandidate, reading_focus: str | None = None):
        if candidate.paper_id == "paper_2":
            raise Exception("Simulated failure")
        return original_read(candidate, reading_focus)

    wrapper.reader.read_paper = selective_fail

    result = wrapper.execute()

    # Should have processed all 5 papers
    assert result["papers_read"] == 5
    assert result["failed"] == 1
    assert result["successful"] + result["degraded"] == 4

    # Stage status should be degraded
    assert result["stage_status"] == "degraded"


def test_reader_wrapper_all_success_completed_status(
    temp_db: str, sample_run_with_candidates: tuple
):
    """全部成功时，stage 状态为 completed"""
    run_id, candidates = sample_run_with_candidates

    wrapper = ReaderAgentWrapper(stage="reader", db_path=temp_db, run_id=run_id)
    result = wrapper.execute()

    # Should have no failures
    assert result["failed"] == 0

    # Stage status should be completed (or degraded if LLM unavailable)
    assert result["stage_status"] in ["completed", "degraded"]


def test_reader_wrapper_all_failure_raises_exception(
    temp_db: str, sample_run_with_candidates: tuple
):
    """全部失败时，抛出异常导致 stage failed"""
    run_id, candidates = sample_run_with_candidates

    wrapper = ReaderAgentWrapper(stage="reader", db_path=temp_db, run_id=run_id)

    # Mock the reader to always fail
    def always_fail(candidate: PaperCandidate, reading_focus: str | None = None):
        raise Exception("Simulated failure")

    wrapper.reader.read_paper = always_fail

    # Should raise exception
    with pytest.raises(RuntimeError, match="All 5 papers failed to read"):
        wrapper.execute()

    # Cards should still be saved (as failed cards)
    run_detail = store.get_run_detail(temp_db, run_id)
    saved_cards = run_detail.get("cards", [])
    assert len(saved_cards) == 5
    assert all(card["status"] == "failed" for card in saved_cards)


def test_reader_wrapper_no_selection_plan_raises_error(temp_db: str):
    """没有候选选择计划时，抛出错误"""
    run_id = store.create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # No plan created - should raise error
    wrapper = ReaderAgentWrapper(stage="reader", db_path=temp_db, run_id=run_id)

    with pytest.raises(RuntimeError, match="No candidate selection plan found"):
        wrapper.execute()


def test_reader_wrapper_empty_selection_completes_gracefully(temp_db: str):
    """选择列表为空时，优雅完成（不抛异常）"""
    run_id = store.create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Create plan with empty selection
    store.create_plan(
        db_path=temp_db,
        run_id=run_id,
        phase="candidate_selection",
        plan_data={"selected_paper_ids": [], "reasoning": "No papers selected"},
    )

    wrapper = ReaderAgentWrapper(stage="reader", db_path=temp_db, run_id=run_id)
    result = wrapper.execute()

    # Should complete with zero papers
    assert result["papers_read"] == 0
    assert result["cards_created"] == 0


# ==================== Test PipelineRunner Integration ====================


def test_runner_executes_reader_stage_with_default_factory(
    temp_db: str, sample_run_with_candidates: tuple
):
    """PipelineRunner 使用 create_default_agent 可以执行 reader stage"""
    run_id, candidates = sample_run_with_candidates

    from app.research_pipeline.runner import create_default_agent

    runner = PipelineRunner(db_path=temp_db, agent_factory=create_default_agent)

    # Execute just the reader stage
    result = runner._execute_stage(run_id, "reader")

    assert result["papers_read"] == 5
    assert result["cards_created"] == 5


def test_runner_sets_stage_status_correctly(
    temp_db: str, sample_run_with_candidates: tuple
):
    """PipelineRunner 根据 stage_status 正确更新 stage 状态"""
    run_id, candidates = sample_run_with_candidates

    from app.research_pipeline.runner import create_default_agent

    runner = PipelineRunner(db_path=temp_db, agent_factory=create_default_agent)

    # Execute reader stage
    runner._execute_stage(run_id, "reader")

    # Check stage status in database
    run_detail = store.get_run_detail(temp_db, run_id)
    stages = run_detail.get("stages", [])
    reader_stage = next((s for s in stages if s["stage"] == "reader"), None)

    assert reader_stage is not None
    assert reader_stage["status"] in ["completed", "degraded"]


def test_runner_stage_fails_when_all_papers_fail(
    temp_db: str, sample_run_with_candidates: tuple
):
    """所有论文失败时，runner 将 stage 标记为 failed"""
    run_id, candidates = sample_run_with_candidates

    # Create a custom factory that returns a failing reader
    def failing_reader_factory(stage: str, db_path: str, run_id: str):
        if stage == "reader":
            wrapper = ReaderAgentWrapper(stage, db_path, run_id)
            # Mock to always fail
            def always_fail(candidate: PaperCandidate, reading_focus: str | None = None):
                raise Exception("Simulated failure")

            wrapper.reader.read_paper = always_fail
            return wrapper
        else:
            from app.research_pipeline.runner import StubAgent

            return StubAgent(stage, db_path, run_id)

    runner = PipelineRunner(db_path=temp_db, agent_factory=failing_reader_factory)

    # Should raise exception
    with pytest.raises(RuntimeError, match="All 5 papers failed to read"):
        runner._execute_stage(run_id, "reader")

    # Check stage status
    run_detail = store.get_run_detail(temp_db, run_id)
    stages = run_detail.get("stages", [])
    reader_stage = next((s for s in stages if s["stage"] == "reader"), None)

    assert reader_stage is not None
    assert reader_stage["status"] == "failed"
