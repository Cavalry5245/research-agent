"""
Tests for ReaderAgent PDF mode.

Tests the PDF reader functionality when local PDF is available.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from app.research_pipeline.agents.reader import ReaderAgent
from app.research_pipeline.schemas import PaperCandidate, PaperCard
from app.schemas import PaperParseResult, Section


@pytest.fixture
def candidate_with_pdf(tmp_path):
    """Create a candidate with local PDF path."""
    # Create a dummy PDF file
    pdf_path = tmp_path / "test_paper.pdf"
    pdf_path.write_text("dummy pdf content")

    return PaperCandidate(
        paper_id="paper_003",
        source="semantic_scholar",
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        year=2017,
        venue="NeurIPS",
        abstract="The dominant sequence transduction models are based on complex RNNs or CNNs.",
        doi="10.5555/example.doi",
        semantic_scholar_id="xyz789",
        url="https://example.com/paper",
        citation_count=50000,
        relevance_score=0.98,
        local_pdf_path=str(pdf_path),
    )


@pytest.fixture
def mock_parse_result():
    """Create a mock PDF parse result."""
    return PaperParseResult(
        paper_id="paper_003",
        title="Attention Is All You Need",
        abstract="The dominant sequence transduction models are based on complex RNNs or CNNs. "
                 "We propose a new architecture, the Transformer, based solely on attention mechanisms.",
        sections=[
            Section(
                heading="Introduction",
                content="Recurrent neural networks have been the dominant approach to sequence modeling. "
                       "However, they are inherently sequential and difficult to parallelize.",
                page_number=1,
            ),
            Section(
                heading="Model Architecture",
                content="The Transformer follows the encoder-decoder structure. "
                       "The encoder maps input sequences to continuous representations.",
                page_number=2,
            ),
            Section(
                heading="Experiments",
                content="We trained on WMT 2014 English-German dataset consisting of 4.5M sentence pairs. "
                       "Our model achieves 28.4 BLEU on the test set.",
                page_number=5,
            ),
            Section(
                heading="Results",
                content="The Transformer achieves state-of-the-art performance on English-to-German translation. "
                       "Training time was reduced by 90% compared to previous models.",
                page_number=6,
            ),
        ],
        full_text="Full text of the paper...",
        pdf_path="/path/to/paper.pdf",
    )


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    with patch("app.research_pipeline.agents.reader.LLMClient") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


def test_pdf_mode_success(mock_llm_client, candidate_with_pdf, mock_parse_result, tmp_path):
    """Test successful PDF extraction."""
    # Mock parse_pdf to return successful result
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.return_value = mock_parse_result

        # Mock LLM response
        mock_llm_client.generate_text.return_value = """
        研究问题: 如何改进序列转导模型，克服RNN的并行化限制
        方法: 基于纯注意力机制的Transformer架构
        数据集: WMT 2014 英德翻译数据集
        指标: BLEU分数
        关键结果: 在英德翻译任务上达到28.4 BLEU，训练时间减少90%
        局限性: 原文未明确说明
        假设: 注意力机制足以替代循环结构
        未来工作: 探索Transformer在其他领域的应用
        """

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_pdf)

        # Verify extraction mode is PDF
        assert card.extraction_mode == "pdf"

        # Verify status is completed
        assert card.status == "completed"

        # Verify basic fields
        assert card.paper_id == "paper_003"
        assert card.title == "Attention Is All You Need"
        assert card.error is None

        # Verify LLM-extracted content
        assert len(card.research_problem) > 0
        assert len(card.method) > 0

        # Verify parse_pdf was called with correct path
        mock_parse_pdf.assert_called_once_with(
            candidate_with_pdf.local_pdf_path,
            candidate_with_pdf.paper_id,
        )


def test_pdf_mode_with_evidence_snippets(mock_llm_client, candidate_with_pdf, mock_parse_result, tmp_path):
    """Test that PDF mode creates evidence with section and page information."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.return_value = mock_parse_result

        mock_llm_client.generate_text.return_value = """
        研究问题: 改进序列模型
        方法: Transformer架构
        数据集: WMT 2014
        指标: BLEU
        关键结果: 28.4 BLEU分数
        """

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_pdf)

        # Verify evidence is created with snippets
        assert len(card.evidence) > 0

        # Each evidence should have snippet and section/page info
        for evidence_item in card.evidence:
            assert "snippet" in evidence_item
            assert evidence_item["snippet"]  # Non-empty
            # At least one of section or page should be present
            assert "section" in evidence_item or "page" in evidence_item


def test_pdf_parse_failure_isolation(mock_llm_client, candidate_with_pdf, tmp_path):
    """Test that PDF parse failure marks card as failed but doesn't crash."""
    # Mock parse_pdf to raise an exception
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.side_effect = FileNotFoundError("PDF file not found")

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_pdf)

        # Verify card is marked as failed/degraded
        assert card.status in ["failed", "degraded"]

        # Verify error message is captured
        assert card.error is not None
        assert "not found" in card.error.lower() or "PDF" in card.error

        # Verify extraction mode attempted PDF
        assert card.extraction_mode == "pdf"

        # Basic metadata should still be present
        assert card.paper_id == "paper_003"
        assert card.title == "Attention Is All You Need"


def test_pdf_parse_corrupted_file(mock_llm_client, candidate_with_pdf, tmp_path):
    """Test handling of corrupted PDF file."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.side_effect = ValueError("无法打开 PDF 文件 (可能已损坏或格式错误)")

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_pdf)

        # Verify graceful degradation
        assert card.status in ["failed", "degraded"]
        assert card.error is not None
        assert "损坏" in card.error or "格式错误" in card.error or "PDF" in card.error

        # Should not crash the entire system
        assert card.paper_id == "paper_003"


def test_pdf_no_text_extracted(mock_llm_client, candidate_with_pdf, tmp_path):
    """Test handling of scanned PDF with no extractable text."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.side_effect = ValueError("PDF 文件无法提取到文本内容，可能为扫描版或图片型 PDF")

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_pdf)

        # Verify error handling
        assert card.status in ["failed", "degraded"]
        assert card.error is not None
        assert "扫描版" in card.error or "图片型" in card.error or "文本" in card.error


def test_pdf_mode_llm_failure_after_parse(mock_llm_client, candidate_with_pdf, mock_parse_result, tmp_path):
    """Test LLM failure after successful PDF parsing."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.return_value = mock_parse_result

        # Mock LLM to fail
        mock_llm_client.generate_text.side_effect = RuntimeError("LLM timeout")

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_pdf)

        # Should still produce a card (degraded)
        assert card.extraction_mode == "pdf"
        assert card.status == "degraded"
        assert card.error is not None

        # Should have basic info from PDF parse result
        assert card.paper_id == "paper_003"
        assert card.title  # Should have title from parse result or candidate


def test_pdf_mode_without_llm(candidate_with_pdf, mock_parse_result, tmp_path):
    """Test PDF extraction when LLM is unavailable (fallback)."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.return_value = mock_parse_result

        # Mock LLM client unavailable
        with patch("app.research_pipeline.agents.reader.LLMClient") as mock_class:
            mock_class.side_effect = ValueError("LLM not configured")

            db_path = str(tmp_path / "test.db")
            agent = ReaderAgent(db_path=db_path)

            card = agent.read_paper(candidate_with_pdf)

    # Should still produce a card with PDF content
    assert card.extraction_mode == "pdf"
    assert card.status == "degraded"
    assert card.error is not None
    assert "LLM" in card.error

    # Should have content from PDF sections
    assert card.paper_id == "paper_003"


def test_evidence_has_required_fields(mock_llm_client, candidate_with_pdf, mock_parse_result, tmp_path):
    """Test that evidence contains required fields: snippet, section/page."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.return_value = mock_parse_result

        mock_llm_client.generate_text.return_value = "研究问题: 测试"

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        card = agent.read_paper(candidate_with_pdf)

        # Verify each evidence has required structure
        for evidence_item in card.evidence:
            # Must have snippet
            assert "snippet" in evidence_item
            assert isinstance(evidence_item["snippet"], str)
            assert len(evidence_item["snippet"]) > 0

            # Must have at least section or page
            has_section = "section" in evidence_item and evidence_item["section"]
            has_page = "page" in evidence_item and evidence_item["page"] is not None
            assert has_section or has_page, "Evidence must have section or page information"


def test_no_old_metadata_json_written(mock_llm_client, candidate_with_pdf, mock_parse_result, tmp_path):
    """Test that reader does not write old paper metadata JSON files."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.return_value = mock_parse_result

        mock_llm_client.generate_text.return_value = "研究问题: 测试"

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        # Record files before
        files_before = set(tmp_path.rglob("*.json"))

        card = agent.read_paper(candidate_with_pdf)

        # Record files after
        files_after = set(tmp_path.rglob("*.json"))

        # Check no new metadata JSON files were created
        new_files = files_after - files_before
        for new_file in new_files:
            # Allow only test.db-related files, not paper metadata JSON
            assert "_parsed.json" not in new_file.name, \
                f"Reader should not write old metadata JSON: {new_file}"


def test_reading_focus_passed_to_pdf_extraction(mock_llm_client, candidate_with_pdf, mock_parse_result, tmp_path):
    """Test that reading_focus parameter works with PDF mode."""
    with patch("app.research_pipeline.agents.reader.parse_pdf") as mock_parse_pdf:
        mock_parse_pdf.return_value = mock_parse_result

        mock_llm_client.generate_text.return_value = "研究问题: 测试"

        db_path = str(tmp_path / "test.db")
        agent = ReaderAgent(db_path=db_path)

        reading_focus = "Focus on experimental methodology and datasets"
        card = agent.read_paper(candidate_with_pdf, reading_focus=reading_focus)

        # Verify LLM was called with reading focus
        assert mock_llm_client.generate_text.called
        call_args = mock_llm_client.generate_text.call_args[0][0]
        assert reading_focus in call_args or "实验" in call_args or "方法" in call_args
