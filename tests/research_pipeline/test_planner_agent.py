"""
Tests for Planner Agent

验证 Planner Agent 的 LLM planning、deterministic fallback 和 candidate selection。
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.research_pipeline import store
from app.research_pipeline.agents.planner import PlannerAgent
from app.research_pipeline.schemas import PaperCandidate


# ==================== Fixtures ====================


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    """创建临时测试数据库"""
    db_path = str(tmp_path / "test_planner.db")
    store.init_db(db_path)
    return db_path


@pytest.fixture
def sample_run_id(temp_db: str) -> str:
    """创建一个测试 run"""
    run_id = store.create_run(
        db_path=temp_db,
        question="What are the latest advances in transformer models?",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    return run_id


@pytest.fixture
def sample_candidates(temp_db: str, sample_run_id: str) -> list[PaperCandidate]:
    """创建测试候选论文"""
    candidates = [
        PaperCandidate(
            paper_id=f"paper_{i}",
            source="semantic_scholar",
            title=f"Paper {i}: Transformer Research",
            authors=[f"Author {i}"],
            year=2020 + i,
            abstract=f"Abstract for paper {i}...",
            citation_count=1000 - i * 100,
        )
        for i in range(10)
    ]

    # Store candidates in DB
    for candidate in candidates:
        store.create_candidate(temp_db, sample_run_id, candidate)

    return candidates


# ==================== Test Initial Phase with LLM Success ====================


def test_initial_phase_llm_success(temp_db: str, sample_run_id: str):
    """LLM 成功返回 JSON 时，保存 normalized question、subquestions、queries、criteria"""

    # Mock LLM response with valid JSON
    mock_llm_response = json.dumps({
        "normalized_question": "What are recent advances in transformer architectures?",
        "subquestions": [
            "What are the key improvements in transformer models since 2020?",
            "What are the emerging variants of transformer architectures?"
        ],
        "queries": [
            "transformer architecture advances 2020-2024",
            "attention mechanism improvements",
            "efficient transformers"
        ],
        "relevance_criteria": [
            "Paper must discuss transformer models",
            "Published after 2019",
            "Contains experimental results"
        ]
    })

    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.return_value = mock_llm_response

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    # Execute initial phase
    plan = planner.plan_initial(
        run_id=sample_run_id,
        question="What are the latest advances in transformer models?",
        source_mode="web_search"
    )

    # Verify plan structure
    assert plan is not None
    assert plan.run_id == sample_run_id
    assert plan.phase == "initial"
    assert plan.version == 1

    # Verify plan_data contents
    plan_data = plan.plan_data
    assert plan_data["normalized_question"] == "What are recent advances in transformer architectures?"
    assert len(plan_data["subquestions"]) == 2
    assert len(plan_data["queries"]) == 3
    assert len(plan_data["relevance_criteria"]) == 3

    # Verify LLM was called
    mock_llm_client.generate_text.assert_called_once()

    # Verify plan was persisted
    stored_plans = store.get_plans_by_run(temp_db, sample_run_id)
    assert len(stored_plans) == 1
    assert stored_plans[0]["phase"] == "initial"


# ==================== Test Initial Phase with LLM Fallback ====================


def test_initial_phase_llm_fallback_on_invalid_json(temp_db: str, sample_run_id: str):
    """LLM 返回无效 JSON 时，使用原问题作为 fallback query"""

    # Mock LLM to return invalid JSON
    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.return_value = "This is not valid JSON at all"

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    question = "What are the latest advances in transformer models?"
    plan = planner.plan_initial(
        run_id=sample_run_id,
        question=question,
        source_mode="web_search"
    )

    # Verify fallback behavior
    assert plan is not None
    plan_data = plan.plan_data
    assert plan_data["normalized_question"] == question
    assert plan_data["queries"] == [question]
    assert plan_data["subquestions"] == []
    assert plan_data["relevance_criteria"] == []
    assert plan_data["fallback_used"] is True


def test_initial_phase_llm_fallback_on_exception(temp_db: str, sample_run_id: str):
    """LLM 调用失败时，使用原问题作为 fallback query"""

    # Mock LLM to raise exception
    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.side_effect = RuntimeError("LLM API 调用失败")

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    question = "What are the latest advances in transformer models?"
    plan = planner.plan_initial(
        run_id=sample_run_id,
        question=question,
        source_mode="web_search"
    )

    # Verify fallback behavior
    assert plan is not None
    plan_data = plan.plan_data
    assert plan_data["normalized_question"] == question
    assert plan_data["queries"] == [question]
    assert plan_data["fallback_used"] is True


# ==================== Test Candidate Selection Phase ====================


def test_candidate_selection_llm_success(temp_db: str, sample_run_id: str, sample_candidates: list):
    """LLM 成功返回候选选择时，最多选择 max_reader_papers 篇"""

    # Mock LLM response with paper selection (select first 5)
    mock_llm_response = json.dumps({
        "selected_paper_ids": [f"paper_{i}" for i in range(5)],
        "reasoning": "Selected top 5 most relevant papers based on citation count and recency"
    })

    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.return_value = mock_llm_response

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    # Execute candidate selection with max_reader_papers=8
    plan = planner.plan_candidate_selection(
        run_id=sample_run_id,
        max_reader_papers=8
    )

    # Verify plan structure
    assert plan is not None
    assert plan.phase == "candidate_selection"
    assert plan.version == 1

    # Verify selection
    plan_data = plan.plan_data
    assert len(plan_data["selected_paper_ids"]) == 5
    assert plan_data["selected_paper_ids"] == [f"paper_{i}" for i in range(5)]

    # Verify plan was persisted
    stored_plans = store.get_plans_by_run(temp_db, sample_run_id)
    assert len(stored_plans) == 1
    assert stored_plans[0]["phase"] == "candidate_selection"


def test_candidate_selection_respects_max_limit(temp_db: str, sample_run_id: str, sample_candidates: list):
    """候选选择阶段最多选择 max_reader_papers 篇论文"""

    # Mock LLM to return more papers than the limit
    mock_llm_response = json.dumps({
        "selected_paper_ids": [f"paper_{i}" for i in range(12)],  # 12 papers
        "reasoning": "Selected papers"
    })

    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.return_value = mock_llm_response

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    # Execute with max_reader_papers=5
    plan = planner.plan_candidate_selection(
        run_id=sample_run_id,
        max_reader_papers=5
    )

    # Verify only first 5 papers are selected
    plan_data = plan.plan_data
    assert len(plan_data["selected_paper_ids"]) == 5
    assert plan_data["selected_paper_ids"] == [f"paper_{i}" for i in range(5)]


def test_candidate_selection_fallback_on_invalid_json(temp_db: str, sample_run_id: str, sample_candidates: list):
    """LLM 返回无效 JSON 时，使用 fallback 选择策略（按 citation_count 降序）"""

    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.return_value = "Invalid JSON response"

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    plan = planner.plan_candidate_selection(
        run_id=sample_run_id,
        max_reader_papers=3
    )

    # Verify fallback selection (top 3 by citation_count)
    plan_data = plan.plan_data
    assert len(plan_data["selected_paper_ids"]) == 3
    assert plan_data["selected_paper_ids"] == ["paper_0", "paper_1", "paper_2"]
    assert plan_data["fallback_used"] is True


def test_candidate_selection_fallback_on_exception(temp_db: str, sample_run_id: str, sample_candidates: list):
    """LLM 调用失败时，使用 fallback 选择策略"""

    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.side_effect = RuntimeError("LLM API failed")

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    plan = planner.plan_candidate_selection(
        run_id=sample_run_id,
        max_reader_papers=4
    )

    # Verify fallback selection
    plan_data = plan.plan_data
    assert len(plan_data["selected_paper_ids"]) == 4
    assert plan_data["fallback_used"] is True


# ==================== Test Store Methods ====================


def test_create_plan(temp_db: str, sample_run_id: str):
    """测试 create_plan 方法"""

    plan_data = {
        "normalized_question": "Test question",
        "queries": ["query1", "query2"],
        "subquestions": []
    }

    plan_id = store.create_plan(
        db_path=temp_db,
        run_id=sample_run_id,
        phase="initial",
        plan_data=plan_data
    )

    assert plan_id is not None
    assert plan_id.startswith("plan_")

    # Verify in DB
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM research_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()

    assert row is not None
    assert row["run_id"] == sample_run_id
    assert row["phase"] == "initial"
    assert row["version"] == 1
    assert json.loads(row["plan_json"]) == plan_data

    conn.close()


def test_get_plans_by_run(temp_db: str, sample_run_id: str):
    """测试 get_plans_by_run 方法"""

    # Create multiple plans
    store.create_plan(
        db_path=temp_db,
        run_id=sample_run_id,
        phase="initial",
        plan_data={"queries": ["q1"]}
    )

    store.create_plan(
        db_path=temp_db,
        run_id=sample_run_id,
        phase="candidate_selection",
        plan_data={"selected_paper_ids": ["p1", "p2"]}
    )

    # Retrieve plans
    plans = store.get_plans_by_run(temp_db, sample_run_id)

    assert len(plans) == 2
    assert plans[0]["phase"] == "initial"
    assert plans[1]["phase"] == "candidate_selection"
    assert plans[0]["version"] == 1
    assert plans[1]["version"] == 2


def test_get_plans_by_run_empty(temp_db: str, sample_run_id: str):
    """测试空结果的情况"""

    plans = store.get_plans_by_run(temp_db, sample_run_id)
    assert plans == []


# ==================== Test Plan Versioning ====================


def test_plan_versioning(temp_db: str, sample_run_id: str):
    """测试 plan version 自动递增"""

    mock_llm_client = MagicMock()
    mock_llm_client.generate_text.return_value = json.dumps({
        "normalized_question": "Q1",
        "queries": ["q1"],
        "subquestions": []
    })

    planner = PlannerAgent(db_path=temp_db, llm_client=mock_llm_client)

    # Create initial plan
    plan1 = planner.plan_initial(sample_run_id, "Question 1", "web_search")
    assert plan1.version == 1

    # Create candidate selection plan
    mock_llm_client.generate_text.return_value = json.dumps({
        "selected_paper_ids": ["p1"],
        "reasoning": "test"
    })

    # Add a candidate first
    store.create_candidate(
        temp_db,
        sample_run_id,
        PaperCandidate(
            paper_id="p1",
            source="semantic_scholar",
            title="Test Paper",
            authors=["Author"],
        )
    )

    plan2 = planner.plan_candidate_selection(sample_run_id, max_reader_papers=5)
    assert plan2.version == 2

    # Verify both plans exist
    all_plans = store.get_plans_by_run(temp_db, sample_run_id)
    assert len(all_plans) == 2
    assert all_plans[0]["version"] == 1
    assert all_plans[1]["version"] == 2
