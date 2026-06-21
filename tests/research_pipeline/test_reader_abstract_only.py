"""
Tests for ReaderAgent abstract-only mode.

Tests the abstract-only reader functionality when no PDF is available.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.research_pipeline.agents.reader import ReaderAgent
from app.research_pipeline.schemas import PaperCandidate, PaperCard


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    with patch("app.research_pipeline.agents.reader.LLMClient") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def candidate_no_pdf():
    """Create a candidate without PDF."""
    return PaperCandidate(
        paper_id="paper_001",
        source="semantic_scholar",
        title="Deep Learning for Natural Language Processing",
        authors=["John Doe", "Jane Smith"],
        year=2023,
        venue="ICLR",
        abstract="This paper presents a novel approach to NLP using deep learning. "
                 "We propose a transformer-based architecture that achieves state-of-the-art "
                 "results on multiple benchmarks. Our method improves upon previous work by "
                 "incorporating attention mechanisms and pre-training strategies.",
        doi="10.1234/example.doi",
        semantic_scholar_id="abc123",
        url="https://example.com/paper",
        citation_count=150,
        relevance_score=0.95,
        local_pdf_path=None,  # No PDF available
    )


@pytest.fixture
def candidate_with_minimal_abstract():
    """Create a candidate with minimal abstract."""
    return PaperCandidate(
        paper_id="paper_002",
        source="arxiv",
        title="Quantum Computing Applications",
        authors=["Alice Johnson"],
        year=2024,
        abstract="Short abstract.",
        local_pdf_path=None,
    )


def test_abstract_only_mode_with_llm(mock_llm_client, candidate_no_pdf, tmp_path):
    """Test abstract-only extraction when LLM is available."""
    # Mock LLM response with structured output
    mock_llm_client.generate_text.return_value = """
    研究问题: 如何使用深度学习改进自然语言处理任务
    方法: 基于Transformer的预训练架构
    数据集: 多个NLP基准数据集
    指标: 准确率、F1分数
    关键结果: 在多个基准测试中达到最先进水平
    局限性: 需要大量计算资源
    假设: 注意力机制对NLP任务有效
    未来工作: 探索更高效的预训练策略
    """

    db_path = str(tmp_path / "test.db")
    agent = ReaderAgent(db_path=db_path)

    card = agent.read_paper(candidate_no_pdf)

    # Verify extraction mode
    assert card.extraction_mode == "abstract_only"

    # Verify basic fields
    assert card.paper_id == "paper_001"
    assert card.title == "Deep Learning for Natural Language Processing"
    assert card.status == "completed"

    # Verify LLM-extracted content
    assert "深度学习" in card.research_problem or "自然语言处理" in card.research_problem
    assert len(card.method) > 0

    # Verify no fabricated evidence (no page/section for abstract-only)
    assert card.error is None


def test_abstract_only_mode_without_llm(candidate_no_pdf, tmp_path):
    """Test abstract-only extraction when LLM is unavailable (fallback)."""
    # Mock LLM client initialization failure
    with patch("app.research_pipeline.agents.reader.LLMClient") as mock_class:
        mock_class.side_effect = ValueError("LLM API Key 未配置")

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_no_pdf)

    # Verify extraction mode
    assert card.extraction_mode == "abstract_only"

    # Verify basic fields
    assert card.paper_id == "paper_001"
    assert card.title == "Deep Learning for Natural Language Processing"
    assert card.status == "degraded"

    # Verify fallback content
    assert card.bibliographic_metadata.get("authors") == ["John Doe", "Jane Smith"]
    assert card.bibliographic_metadata.get("year") == 2023
    assert card.bibliographic_metadata.get("venue") == "ICLR"

    # Abstract should be used as research problem or summary
    assert len(card.research_problem) > 0 or "abstract" in card.bibliographic_metadata

    # Verify degraded reason in error field
    assert card.error is not None
    assert "LLM" in card.error or "不可用" in card.error


def test_abstract_only_no_fake_evidence(mock_llm_client, candidate_no_pdf, tmp_path):
    """Test that abstract-only mode does not fabricate page/section evidence."""
    mock_llm_client.generate_text.return_value = """
    研究问题: NLP任务改进
    方法: Transformer架构
    """

    db_path = str(tmp_path / "test.db")
    agent = ReaderAgent(db_path=db_path)

    card = agent.read_paper(candidate_no_pdf)

    # Verify no evidence with page/section is created in abstract-only mode
    # Evidence list should be empty or only contain abstract-level evidence
    for evidence_item in card.evidence:
        # In abstract-only mode, evidence should not have page numbers or sections
        # from the PDF body
        assert evidence_item.get("page") is None or evidence_item.get("source") == "abstract"
        assert evidence_item.get("section") is None or evidence_item.get("source") == "abstract"


def test_minimal_abstract_fallback(candidate_with_minimal_abstract, tmp_path):
    """Test graceful handling of minimal abstract."""
    # Mock LLM unavailable
    with patch("app.research_pipeline.agents.reader.LLMClient") as mock_class:
        mock_class.side_effect = ValueError("LLM not configured")

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_minimal_abstract)

    # Should still produce a valid card
    assert card.extraction_mode == "abstract_only"
    assert card.paper_id == "paper_002"
    assert card.title == "Quantum Computing Applications"
    assert card.status == "degraded"
    assert card.error is not None


def test_llm_failure_during_extraction(mock_llm_client, candidate_no_pdf, tmp_path):
    """Test handling of LLM failure during extraction."""
    # Mock LLM to raise an exception
    mock_llm_client.generate_text.side_effect = RuntimeError("LLM API timeout")

    db_path = str(tmp_path / "test.db")
    agent = ReaderAgent(db_path=db_path)

    card = agent.read_paper(candidate_no_pdf)

    # Should fall back to degraded mode
    assert card.extraction_mode == "abstract_only"
    assert card.status == "degraded"
    assert card.error is not None
    assert "LLM" in card.error or "timeout" in card.error.lower()

    # Should still have basic metadata
    assert card.title == "Deep Learning for Natural Language Processing"
    assert len(card.bibliographic_metadata) > 0


def test_reading_focus_parameter(mock_llm_client, candidate_no_pdf, tmp_path):
    """Test that reading_focus parameter is passed to LLM prompt."""
    mock_llm_client.generate_text.return_value = "研究问题: 测试"

    db_path = str(tmp_path / "test.db")
    agent = ReaderAgent(db_path=db_path)

    reading_focus = "Focus on methodology and datasets"
    card = agent.read_paper(candidate_no_pdf, reading_focus=reading_focus)

    # Verify LLM was called
    assert mock_llm_client.generate_text.called

    # Verify reading focus was included in prompt
    call_args = mock_llm_client.generate_text.call_args[0][0]
    assert reading_focus in call_args or "方法" in call_args


def test_bibliographic_metadata_population(mock_llm_client, candidate_no_pdf, tmp_path):
    """Test that bibliographic metadata is properly populated."""
    mock_llm_client.generate_text.return_value = "研究问题: 测试"

    db_path = str(tmp_path / "test.db")
    agent = ReaderAgent(db_path=db_path)

    card = agent.read_paper(candidate_no_pdf)

    # Verify bibliographic metadata
    assert card.bibliographic_metadata is not None
    assert card.bibliographic_metadata.get("authors") == ["John Doe", "Jane Smith"]
    assert card.bibliographic_metadata.get("year") == 2023
    assert card.bibliographic_metadata.get("venue") == "ICLR"
    assert card.bibliographic_metadata.get("doi") == "10.1234/example.doi"
    assert card.bibliographic_metadata.get("source") == "semantic_scholar"
