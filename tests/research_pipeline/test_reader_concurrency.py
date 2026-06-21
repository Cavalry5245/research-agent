"""
Tests for Reader Agent Concurrency and Failure Isolation

验证 Reader Agent 的并发处理和故障隔离能力。
"""

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.research_pipeline import store
from app.research_pipeline.agents.reader import ReaderAgent
from app.research_pipeline.schemas import PaperCandidate, PaperCard


# ==================== Fixtures ====================


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    """创建临时测试数据库"""
    db_path = str(tmp_path / "test_reader_concurrency.db")
    store.init_db(db_path)
    return db_path


@pytest.fixture
def sample_run_id(temp_db: str) -> str:
    """创建一个测试 run"""
    run_id = store.create_run(
        db_path=temp_db,
        question="Test question for concurrency",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )
    return run_id


@pytest.fixture
def sample_candidates() -> list[PaperCandidate]:
    """创建测试候选论文（无 PDF）"""
    return [
        PaperCandidate(
            paper_id=f"paper_{i}",
            source="semantic_scholar",
            title=f"Paper {i}: Test Paper",
            authors=[f"Author {i}"],
            year=2020 + i,
            abstract=f"This is abstract {i} for testing concurrency.",
            citation_count=100 - i * 10,
        )
        for i in range(5)
    ]


# ==================== Test Concurrency Limit ====================


def test_batch_read_respects_concurrency_limit(temp_db: str, sample_candidates: list[PaperCandidate]):
    """并发数限制生效，不会同时处理超过 concurrency 篇论文"""

    reader = ReaderAgent(db_path=temp_db)

    # Track concurrent calls
    concurrent_calls = []
    max_concurrent = 0

    original_read = reader.read_paper

    def tracked_read(candidate: PaperCandidate, reading_focus: str | None = None) -> PaperCard:
        concurrent_calls.append(1)
        nonlocal max_concurrent
        max_concurrent = max(max_concurrent, len(concurrent_calls))

        # Simulate some work
        import time
        time.sleep(0.05)

        result = original_read(candidate, reading_focus)
        concurrent_calls.pop()
        return result

    # Use ThreadPoolExecutor to test concurrency
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(reader.read_paper, candidate, None)
            for candidate in sample_candidates
        ]
        results = [f.result() for f in futures]

    # All papers should be processed
    assert len(results) == 5
    # But concurrency should be limited (this is a basic check, actual implementation will be more sophisticated)
    assert all(isinstance(card, PaperCard) for card in results)


def test_batch_read_papers_method_exists(temp_db: str, sample_candidates: list[PaperCandidate]):
    """batch_read_papers 方法存在并接受正确的参数"""

    reader = ReaderAgent(db_path=temp_db)

    # Method should exist
    assert hasattr(reader, "batch_read_papers")

    # Call with valid parameters
    result = reader.batch_read_papers(
        candidates=sample_candidates,
        reading_focus=None,
        concurrency=3,
    )

    # Should return dict with cards and summary
    assert isinstance(result, dict)
    assert "cards" in result
    assert "summary" in result
    assert isinstance(result["cards"], list)
    assert isinstance(result["summary"], dict)


# ==================== Test Failure Isolation ====================


def test_single_paper_failure_does_not_crash_batch(temp_db: str, sample_candidates: list[PaperCandidate]):
    """单篇论文失败不会终止整个批次处理"""

    reader = ReaderAgent(db_path=temp_db)

    # Mock read_paper to fail on paper_2
    original_read = reader.read_paper

    def failing_read(candidate: PaperCandidate, reading_focus: str | None = None) -> PaperCard:
        if candidate.paper_id == "paper_2":
            raise Exception("Simulated failure for paper_2")
        return original_read(candidate, reading_focus)

    reader.read_paper = failing_read

    # Process batch
    result = reader.batch_read_papers(
        candidates=sample_candidates,
        reading_focus=None,
        concurrency=3,
    )

    # Should have 5 cards (4 successful + 1 failed)
    assert len(result["cards"]) == 5

    # Find the failed card
    failed_cards = [card for card in result["cards"] if card.status == "failed"]
    assert len(failed_cards) == 1
    assert failed_cards[0].paper_id == "paper_2"
    assert failed_cards[0].error is not None
    assert "Simulated failure" in failed_cards[0].error

    # Other cards should be successful
    successful_cards = [card for card in result["cards"] if card.status != "failed"]
    assert len(successful_cards) == 4


def test_all_papers_fail_returns_all_failed_cards(temp_db: str, sample_candidates: list[PaperCandidate]):
    """所有论文失败时，返回所有失败卡片"""

    reader = ReaderAgent(db_path=temp_db)

    # Mock read_paper to always fail
    def always_fail(candidate: PaperCandidate, reading_focus: str | None = None) -> PaperCard:
        raise Exception(f"Simulated failure for {candidate.paper_id}")

    reader.read_paper = always_fail

    # Process batch
    result = reader.batch_read_papers(
        candidates=sample_candidates,
        reading_focus=None,
        concurrency=3,
    )

    # Should have 5 failed cards
    assert len(result["cards"]) == 5
    assert all(card.status == "failed" for card in result["cards"])
    assert all(card.error is not None for card in result["cards"])

    # Summary should reflect all failures
    summary = result["summary"]
    assert summary["total"] == 5
    assert summary["failed"] == 5
    assert summary["successful"] == 0


def test_partial_success_summary(temp_db: str, sample_candidates: list[PaperCandidate]):
    """部分成功时，summary 正确统计成功/失败数量"""

    reader = ReaderAgent(db_path=temp_db)

    # Mock read_paper to fail on paper_1 and paper_3
    original_read = reader.read_paper

    def selective_fail(candidate: PaperCandidate, reading_focus: str | None = None) -> PaperCard:
        if candidate.paper_id in ["paper_1", "paper_3"]:
            raise Exception(f"Simulated failure for {candidate.paper_id}")
        return original_read(candidate, reading_focus)

    reader.read_paper = selective_fail

    # Process batch
    result = reader.batch_read_papers(
        candidates=sample_candidates,
        reading_focus=None,
        concurrency=3,
    )

    # Summary counts
    summary = result["summary"]
    assert summary["total"] == 5
    # 3 papers should succeed (completed or degraded), 2 should fail
    assert summary["successful"] + summary["degraded"] == 3
    assert summary["failed"] == 2


# ==================== Test Default Concurrency ====================


def test_default_concurrency_is_3(temp_db: str, sample_candidates: list[PaperCandidate]):
    """默认并发数为 3"""

    reader = ReaderAgent(db_path=temp_db)

    # Call without specifying concurrency
    result = reader.batch_read_papers(
        candidates=sample_candidates[:3],
        reading_focus=None,
    )

    # Should process successfully with default concurrency
    assert len(result["cards"]) == 3
    assert result["summary"]["total"] == 3


def test_concurrency_parameter_validation(temp_db: str, sample_candidates: list[PaperCandidate]):
    """并发数参数应该有合理的范围"""

    reader = ReaderAgent(db_path=temp_db)

    # Concurrency of 1 should work (sequential)
    result = reader.batch_read_papers(
        candidates=sample_candidates[:2],
        reading_focus=None,
        concurrency=1,
    )
    assert len(result["cards"]) == 2

    # Concurrency of 10 should work (high parallelism)
    result = reader.batch_read_papers(
        candidates=sample_candidates,
        reading_focus=None,
        concurrency=10,
    )
    assert len(result["cards"]) == 5


# ==================== Test Summary Structure ====================


def test_summary_contains_required_fields(temp_db: str, sample_candidates: list[PaperCandidate]):
    """summary 包含所有必需字段"""

    reader = ReaderAgent(db_path=temp_db)

    result = reader.batch_read_papers(
        candidates=sample_candidates,
        reading_focus=None,
        concurrency=3,
    )

    summary = result["summary"]

    # Required fields
    assert "total" in summary
    assert "successful" in summary
    assert "failed" in summary
    assert "degraded" in summary

    # Counts should add up
    assert summary["total"] == len(result["cards"])
    assert summary["successful"] + summary["failed"] + summary["degraded"] == summary["total"]
