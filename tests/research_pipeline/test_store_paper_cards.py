"""
Tests for PaperCard store methods.

验证 PaperCard 和 evidence 的持久化。
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.research_pipeline.schemas import PaperCard
from app.research_pipeline.store import (
    create_candidate,
    create_evidence,
    create_paper_card,
    create_run,
    get_evidence,
    get_paper_cards,
    get_run_detail,
    init_db,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_pipeline.db")
        init_db(db_path)
        yield db_path


@pytest.fixture
def test_run(temp_db):
    """Create a test run."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=2,
    )
    return temp_db, run_id


@pytest.fixture
def test_candidate(test_run):
    """Create a test candidate."""
    db_path, run_id = test_run

    from app.research_pipeline.schemas import PaperCandidate

    candidate = PaperCandidate(
        paper_id="paper_001",
        source="semantic_scholar",
        title="Test Paper",
        authors=["张三", "李四"],
        year=2024,
        venue="AAAI",
        abstract="This is a test abstract.",
    )

    candidate_id = create_candidate(db_path, run_id, candidate)
    return db_path, run_id, candidate_id, candidate


def test_create_paper_card_completed(test_candidate):
    """Test creating a completed PaperCard."""
    db_path, run_id, candidate_id, candidate = test_candidate

    paper_card = PaperCard(
        paper_id=candidate.paper_id,
        status="completed",
        extraction_mode="pdf",
        title=candidate.title,
        bibliographic_metadata={"authors": candidate.authors, "year": candidate.year},
        research_problem="研究问题：如何提升模型性能",
        method="使用了深度学习方法",
        datasets=["ImageNet", "COCO"],
        metrics=["Accuracy", "F1"],
        key_results=["准确率达到95%", "F1分数为0.92"],
        limitations=["数据集较小", "计算成本高"],
        assumptions=["假设数据独立同分布"],
        future_work=["未来将扩展到多模态"],
        claims=[{"text": "Our method outperforms baseline", "type": "result"}],
        evidence=[{"snippet": "We achieved 95% accuracy", "section": "Results"}],
    )

    card_id = create_paper_card(db_path, run_id, paper_card)

    assert card_id.startswith("card_")

    # Verify in database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM paper_cards WHERE id = ?", (card_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["run_id"] == run_id
    assert row["paper_id"] == candidate.paper_id
    assert row["status"] == "completed"
    assert row["extraction_mode"] == "pdf"
    assert row["title"] == candidate.title

    # Verify JSON fields preserve UTF-8
    biblio = json.loads(row["bibliographic_json"])
    assert biblio["authors"] == ["张三", "李四"]

    assert row["research_problem"] == "研究问题：如何提升模型性能"
    assert row["method"] == "使用了深度学习方法"

    datasets = json.loads(row["datasets_json"])
    assert datasets == ["ImageNet", "COCO"]

    metrics = json.loads(row["metrics_json"])
    assert metrics == ["Accuracy", "F1"]

    key_results = json.loads(row["key_results_json"])
    assert "准确率达到95%" in key_results

    limitations = json.loads(row["limitations_json"])
    assert "数据集较小" in limitations

    assumptions = json.loads(row["assumptions_json"])
    assert "假设数据独立同分布" in assumptions

    future_work = json.loads(row["future_work_json"])
    assert "未来将扩展到多模态" in future_work


def test_create_paper_card_degraded(test_candidate):
    """Test creating a degraded PaperCard (abstract-only extraction)."""
    db_path, run_id, candidate_id, candidate = test_candidate

    paper_card = PaperCard(
        paper_id=candidate.paper_id,
        status="degraded",
        extraction_mode="abstract_only",
        title=candidate.title,
        bibliographic_metadata={"authors": candidate.authors},
        research_problem="从摘要提取的研究问题",
        method="",
        datasets=[],
        metrics=[],
        key_results=[],
        limitations=[],
        assumptions=[],
        future_work=[],
        claims=[],
        evidence=[],
        error="PDF extraction failed, fallback to abstract",
    )

    card_id = create_paper_card(db_path, run_id, paper_card)

    assert card_id.startswith("card_")

    # Verify degraded status
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status, extraction_mode, error FROM paper_cards WHERE id = ?", (card_id,))
    row = cursor.fetchone()
    conn.close()

    assert row[0] == "degraded"
    assert row[1] == "abstract_only"
    assert row[2] == "PDF extraction failed, fallback to abstract"


def test_create_paper_card_failed(test_candidate):
    """Test creating a failed PaperCard."""
    db_path, run_id, candidate_id, candidate = test_candidate

    paper_card = PaperCard(
        paper_id=candidate.paper_id,
        status="failed",
        extraction_mode="pdf",
        title=candidate.title,
        bibliographic_metadata={},
        error="Extraction completely failed",
    )

    card_id = create_paper_card(db_path, run_id, paper_card)

    assert card_id.startswith("card_")

    # Verify failed status
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status, error FROM paper_cards WHERE id = ?", (card_id,))
    row = cursor.fetchone()
    conn.close()

    assert row[0] == "failed"
    assert row[1] == "Extraction completely failed"


def test_create_evidence(test_candidate):
    """Test creating evidence records."""
    db_path, run_id, candidate_id, candidate = test_candidate

    # First create a paper card
    paper_card = PaperCard(
        paper_id=candidate.paper_id,
        status="completed",
        extraction_mode="pdf",
        title=candidate.title,
    )
    card_id = create_paper_card(db_path, run_id, paper_card)

    # Create evidence
    evidence = {
        "snippet": "我们的方法在ImageNet上达到了95%的准确率。",
        "section": "实验结果",
        "page": 5,
        "source_url": "http://example.com/paper.pdf",
        "evidence_type": "result",
        "confidence": 0.95,
        "metadata": {"table_id": "Table 3"},
    }

    evidence_id = create_evidence(db_path, run_id, candidate.paper_id, evidence)

    assert evidence_id.startswith("evid_")

    # Verify in database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM paper_evidence WHERE id = ?", (evidence_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["run_id"] == run_id
    assert row["paper_id"] == candidate.paper_id
    assert row["paper_card_id"] == card_id
    assert row["snippet"] == "我们的方法在ImageNet上达到了95%的准确率。"
    assert row["section"] == "实验结果"
    assert row["page"] == 5
    assert row["evidence_type"] == "result"
    assert row["confidence"] == 0.95

    metadata = json.loads(row["metadata_json"])
    assert metadata["table_id"] == "Table 3"


def test_get_paper_cards(test_candidate):
    """Test retrieving paper cards for a run."""
    db_path, run_id, candidate_id, candidate = test_candidate

    from app.research_pipeline.schemas import PaperCandidate

    # Create a second candidate for paper_002
    candidate2 = PaperCandidate(
        paper_id="paper_002",
        source="semantic_scholar",
        title="Paper 2",
        authors=["Author 2"],
        year=2024,
    )
    create_candidate(db_path, run_id, candidate2)

    # Create multiple cards
    card1 = PaperCard(
        paper_id="paper_001",
        status="completed",
        extraction_mode="pdf",
        title="Paper 1",
        research_problem="问题1",
    )

    card2 = PaperCard(
        paper_id="paper_002",
        status="degraded",
        extraction_mode="abstract_only",
        title="Paper 2",
        research_problem="问题2",
    )

    create_paper_card(db_path, run_id, card1)
    create_paper_card(db_path, run_id, card2)

    # Retrieve cards
    cards = get_paper_cards(db_path, run_id)

    assert len(cards) == 2
    assert cards[0]["paper_id"] == "paper_001"
    assert cards[0]["status"] == "completed"
    assert cards[0]["research_problem"] == "问题1"

    assert cards[1]["paper_id"] == "paper_002"
    assert cards[1]["status"] == "degraded"
    assert cards[1]["research_problem"] == "问题2"


def test_get_evidence_by_run(test_candidate):
    """Test retrieving all evidence for a run."""
    db_path, run_id, candidate_id, candidate = test_candidate

    # Create card
    paper_card = PaperCard(
        paper_id=candidate.paper_id,
        status="completed",
        extraction_mode="pdf",
        title=candidate.title,
    )
    create_paper_card(db_path, run_id, paper_card)

    # Create multiple evidence records
    evidence1 = {
        "snippet": "证据1：准确率95%",
        "section": "Results",
        "evidence_type": "result",
        "confidence": 0.9,
    }

    evidence2 = {
        "snippet": "证据2：F1分数0.92",
        "section": "Results",
        "evidence_type": "result",
        "confidence": 0.85,
    }

    create_evidence(db_path, run_id, candidate.paper_id, evidence1)
    create_evidence(db_path, run_id, candidate.paper_id, evidence2)

    # Retrieve all evidence for run
    all_evidence = get_evidence(db_path, run_id)

    assert len(all_evidence) == 2
    assert all_evidence[0]["snippet"] == "证据1：准确率95%"
    assert all_evidence[1]["snippet"] == "证据2：F1分数0.92"


def test_get_evidence_by_paper(test_candidate):
    """Test retrieving evidence filtered by paper_id."""
    db_path, run_id, candidate_id, candidate = test_candidate

    from app.research_pipeline.schemas import PaperCandidate

    # Create a second candidate for paper_002
    candidate2 = PaperCandidate(
        paper_id="paper_002",
        source="semantic_scholar",
        title="Paper 2",
        authors=["Author 2"],
        year=2024,
    )
    create_candidate(db_path, run_id, candidate2)

    # Create two paper cards
    card1 = PaperCard(
        paper_id="paper_001",
        status="completed",
        extraction_mode="pdf",
        title="Paper 1",
    )
    card2 = PaperCard(
        paper_id="paper_002",
        status="completed",
        extraction_mode="pdf",
        title="Paper 2",
    )

    create_paper_card(db_path, run_id, card1)
    create_paper_card(db_path, run_id, card2)

    # Create evidence for both papers
    evidence1 = {
        "snippet": "Paper 1 evidence",
        "evidence_type": "result",
    }

    evidence2 = {
        "snippet": "Paper 2 evidence",
        "evidence_type": "method",
    }

    create_evidence(db_path, run_id, "paper_001", evidence1)
    create_evidence(db_path, run_id, "paper_002", evidence2)

    # Retrieve evidence for paper_001 only
    paper1_evidence = get_evidence(db_path, run_id, paper_id="paper_001")

    assert len(paper1_evidence) == 1
    assert paper1_evidence[0]["snippet"] == "Paper 1 evidence"
    assert paper1_evidence[0]["paper_id"] == "paper_001"


def test_get_run_detail_includes_cards(test_candidate):
    """Test that get_run_detail includes paper cards."""
    db_path, run_id, candidate_id, candidate = test_candidate

    # Create a paper card
    paper_card = PaperCard(
        paper_id=candidate.paper_id,
        status="completed",
        extraction_mode="pdf",
        title=candidate.title,
        research_problem="测试研究问题",
        key_results=["结果1", "结果2"],
    )

    create_paper_card(db_path, run_id, paper_card)

    # Get run detail
    detail = get_run_detail(db_path, run_id)

    assert detail is not None
    assert "cards" in detail
    assert len(detail["cards"]) == 1

    card = detail["cards"][0]
    assert card["paper_id"] == candidate.paper_id
    assert card["status"] == "completed"
    assert card["research_problem"] == "测试研究问题"
    assert card["key_results"] == ["结果1", "结果2"]


def test_utf8_preservation(test_candidate):
    """Test that Chinese characters are preserved without escaping."""
    db_path, run_id, candidate_id, candidate = test_candidate

    paper_card = PaperCard(
        paper_id=candidate.paper_id,
        status="completed",
        extraction_mode="pdf",
        title="深度学习在自然语言处理中的应用",
        research_problem="如何提升中文文本分类的准确率？",
        method="我们提出了一种基于Transformer的新方法",
        key_results=["在中文数据集上达到了最先进的性能"],
    )

    create_paper_card(db_path, run_id, paper_card)

    # Retrieve and verify
    cards = get_paper_cards(db_path, run_id)

    assert len(cards) == 1
    assert cards[0]["title"] == "深度学习在自然语言处理中的应用"
    assert cards[0]["research_problem"] == "如何提升中文文本分类的准确率？"
    assert cards[0]["method"] == "我们提出了一种基于Transformer的新方法"
    assert cards[0]["key_results"][0] == "在中文数据集上达到了最先进的性能"

    # Verify raw JSON in database doesn't escape Chinese
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key_results_json FROM paper_cards WHERE paper_id = ?", (candidate.paper_id,))
    raw_json = cursor.fetchone()[0]
    conn.close()

    # Should contain Chinese characters directly, not escaped Unicode
    assert "在中文数据集上达到了最先进的性能" in raw_json
    assert "\\u" not in raw_json  # No Unicode escape sequences
