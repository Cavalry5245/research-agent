import json
import os
import sys
import tempfile

import fitz
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import PaperParseResult
from app.services.pdf_parser import (
    _classify_block_type,
    _sort_blocks_by_reading_order,
    generate_paper_id,
    generate_pdf_profile,
    parse_pdf,
    parse_structured_elements,
    save_parse_result,
)


def _create_test_pdf(filepath: str):
    """Create a minimal academic-style PDF for testing."""
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "A Novel Approach to Infrared Small Target Detection\n"
        "John Doe, Jane Smith\n"
        "Abstract\n"
        "This paper presents a novel approach to infrared small target detection "
        "using vision-language models. We propose a method that combines spatial "
        "attention with semantic guidance to improve detection accuracy.\n"
        "Introduction\n"
        "Infrared small target detection is a critical task in surveillance systems. "
        "Traditional methods rely on local contrast measures, which are limited in "
        "complex backgrounds. Recent advances in deep learning have opened new possibilities "
        "for this task.\n"
        "Related Work\n"
        "Previous approaches include local contrast methods, low-rank decomposition, "
        "and deep learning based detectors. Each has its strengths and limitations "
        "when applied to infrared imagery.\n"
        "Method\n"
        "Our proposed method integrates a vision-language model with a spatial "
        "attention mechanism. The model processes infrared images through a multi-scale "
        "feature extractor, followed by a cross-attention module that aligns visual features "
        "with textual descriptions of target characteristics.\n"
        "Experiments\n"
        "We evaluate our method on three benchmark datasets: SIRST, IRSTD-1K, and NUDT-SIRST. "
        "Our approach achieves state-of-the-art performance with an average precision of 0.95 "
        "and a recall of 0.93.\n"
        "Conclusion\n"
        "We have presented a novel VLM-based approach for infrared small target detection "
        "that achieves superior performance across multiple benchmarks. The integration "
        "of semantic guidance proves effective in reducing false alarms.\n"
        "References\n"
        "[1] Doe et al., Previous Work, CVPR 2023.\n"
        "[2] Smith et al., Another Method, ICCV 2024.\n"
    )
    rect = fitz.Rect(50, 50, 550, 800)
    page.insert_textbox(rect, text, fontsize=12)
    doc.save(filepath)
    doc.close()


def test_generate_paper_id():
    pid = generate_paper_id()
    assert pid.startswith("paper_"), f"Expected paper_id format, got {pid}"
    assert len(pid) > 10

    pid2 = generate_paper_id()
    assert pid2.startswith("paper_")


def test_generate_paper_id_with_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        pid1 = generate_paper_id(tmpdir)
        assert pid1.endswith("_001")

        # Add a fake PDF to simulate existing files
        with open(os.path.join(tmpdir, "existing.pdf"), "w") as f:
            f.write("fake")

        pid2 = generate_paper_id(tmpdir)
        assert pid2.endswith("_002")


def test_parse_pdf_title():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)
        result = parse_pdf(pdf_path, "paper_test_001")
        assert isinstance(result, PaperParseResult)
        assert "Infrared Small Target Detection" in result.title
        assert "A Novel Approach" in result.title


def test_parse_pdf_abstract():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)
        result = parse_pdf(pdf_path, "paper_test_001")
        assert "infrared small target detection" in result.abstract.lower()
        assert "vision-language" in result.abstract


def test_parse_pdf_sections():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)
        result = parse_pdf(pdf_path, "paper_test_001")
        headings = [s.heading for s in result.sections]
        assert "Introduction" in headings
        assert "Related Work" in headings
        assert "Method" in headings
        assert "Experiments" in headings
        assert "Conclusion" in headings
        assert "References" in headings

        method_section = next(s for s in result.sections if s.heading == "Method")
        assert "vision-language model" in method_section.content
        assert method_section.page_number == 1


def test_parse_pdf_full_text():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)
        result = parse_pdf(pdf_path, "paper_test_001")
        assert len(result.full_text) > 200
        assert "SIRST" in result.full_text


def test_save_parse_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)
        result = parse_pdf(pdf_path, "paper_test_001")
        metadata_dir = os.path.join(tmpdir, "metadata")
        saved_path = save_parse_result(result, metadata_dir)

        assert os.path.exists(saved_path)
        assert saved_path.endswith("paper_test_001_parsed.json")

        with open(saved_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["paper_id"] == "paper_test_001"
        assert data["title"]
        assert len(data["sections"]) > 0
        assert data["full_text"]


def test_parse_pdf_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_pdf("nonexistent_file.pdf", "paper_test_001")


def test_parse_pdf_corrupted():
    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_path = os.path.join(tmpdir, "corrupt.pdf")
        with open(corrupt_path, "w") as f:
            f.write("this is not a valid PDF")
        with pytest.raises(ValueError, match="无法打开 PDF"):
            parse_pdf(corrupt_path, "paper_test_001")


def test_parse_pdf_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        doc = fitz.open()
        doc.new_page()
        empty_path = os.path.join(tmpdir, "empty.pdf")
        doc.save(empty_path)
        doc.close()
        with pytest.raises(ValueError, match="无法提取到文本"):
            parse_pdf(empty_path, "paper_test_001")


# ==================== Tests for Task 2.2: Structured Element Parsing ====================


def test_sort_blocks_by_reading_order_double_column():
    """测试双栏阅读顺序排序"""
    page_width = 600.0
    blocks = [
        {"bbox": [50, 100, 250, 150], "id": "left-top"},
        {"bbox": [350, 100, 550, 150], "id": "right-top"},
        {"bbox": [50, 200, 250, 250], "id": "left-mid"},
        {"bbox": [350, 200, 550, 250], "id": "right-mid"},
        {"bbox": [50, 300, 250, 350], "id": "left-bottom"},
        {"bbox": [350, 300, 550, 350], "id": "right-bottom"},
    ]

    sorted_blocks = _sort_blocks_by_reading_order(blocks, page_width, "double_column")
    expected_order = [
        "left-top",
        "left-mid",
        "left-bottom",
        "right-top",
        "right-mid",
        "right-bottom",
    ]
    actual_order = [b["id"] for b in sorted_blocks]

    assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"


def test_sort_blocks_by_reading_order_single_column():
    """测试单栏阅读顺序排序"""
    page_width = 600.0
    blocks = [
        {"bbox": [50, 200, 250, 250], "id": "mid"},
        {"bbox": [50, 100, 250, 150], "id": "top"},
        {"bbox": [50, 300, 250, 350], "id": "bottom"},
    ]

    sorted_blocks = _sort_blocks_by_reading_order(blocks, page_width, "single_column")
    expected_order = ["top", "mid", "bottom"]
    actual_order = [b["id"] for b in sorted_blocks]

    assert actual_order == expected_order


def test_classify_block_type_title():
    """测试标题识别"""
    doc = fitz.open()
    page = doc.new_page()

    block = {
        "type": 0,
        "bbox": [50, 50, 550, 100],
        "lines": [
            {
                "spans": [
                    {"text": "A Novel Approach to Detection", "size": 18}
                ]
            }
        ],
    }

    block_type = _classify_block_type(block, 0, doc)
    doc.close()

    assert block_type == "title"


def test_classify_block_type_heading():
    """测试章节标题识别"""
    doc = fitz.open()

    # Test Introduction
    block1 = {
        "type": 0,
        "bbox": [50, 100, 550, 120],
        "lines": [{"spans": [{"text": "Introduction", "size": 12}]}],
    }
    assert _classify_block_type(block1, 1, doc) == "heading"

    # Test numbered heading
    block2 = {
        "type": 0,
        "bbox": [50, 100, 550, 120],
        "lines": [{"spans": [{"text": "1. Method", "size": 12}]}],
    }
    assert _classify_block_type(block2, 1, doc) == "heading"

    doc.close()


def test_classify_block_type_reference():
    """测试参考文献识别"""
    doc = fitz.open()

    block = {
        "type": 0,
        "bbox": [50, 100, 550, 120],
        "lines": [
            {
                "spans": [
                    {"text": "[1] Doe et al., Some Paper, CVPR 2023.", "size": 10}
                ]
            }
        ],
    }

    assert _classify_block_type(block, 5, doc) == "reference"
    doc.close()


def test_classify_block_type_table():
    """测试表格识别"""
    doc = fitz.open()

    block = {
        "type": 0,
        "bbox": [50, 100, 550, 120],
        "lines": [
            {
                "spans": [
                    {"text": "Method    Precision    Recall    F1", "size": 10}
                ]
            }
        ],
    }

    assert _classify_block_type(block, 3, doc) == "table"
    doc.close()


def test_classify_block_type_figure_caption():
    """测试图注识别"""
    doc = fitz.open()

    # Image block (type == 1)
    block = {"type": 1, "bbox": [50, 100, 550, 300]}

    assert _classify_block_type(block, 2, doc) == "figure_caption"
    doc.close()


def test_generate_pdf_profile():
    """测试 PDF Profile 生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)

        doc = fitz.open(pdf_path)
        profile = generate_pdf_profile(doc, "paper_test_001")
        doc.close()

        assert profile.paper_id == "paper_test_001"
        assert profile.page_count == 1
        assert profile.is_text_pdf is True
        assert profile.layout_type in ["single_column", "double_column", "unknown"]
        assert profile.text_density > 0
        assert isinstance(profile.has_tables, bool)
        assert isinstance(profile.has_figures, bool)


def test_generate_pdf_profile_scanned():
    """测试扫描版 PDF 的 Profile 生成（应该抛出异常）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create an empty page (no text)
        doc = fitz.open()
        doc.new_page()
        empty_path = os.path.join(tmpdir, "empty.pdf")
        doc.save(empty_path)
        doc.close()

        doc = fitz.open(empty_path)
        with pytest.raises(ValueError, match="扫描版或图片型"):
            generate_pdf_profile(doc, "paper_test_001")
        doc.close()


def test_parse_structured_elements():
    """测试结构化元素解析"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)

        doc = fitz.open(pdf_path)
        elements = parse_structured_elements(doc, "paper_test_001", "single_column")
        doc.close()

        # 验证基本属性
        assert len(elements) > 0, "Should extract at least some elements"

        # 验证元素结构
        for elem in elements:
            assert elem.paper_id == "paper_test_001"
            assert elem.element_id.startswith("paper_test_001_elem_")
            assert elem.type in [
                "title",
                "abstract",
                "heading",
                "paragraph",
                "table",
                "figure_caption",
                "equation",
                "reference",
            ]
            assert elem.page_number >= 1
            assert elem.bbox is not None
            assert len(elem.bbox) == 4
            assert elem.order_index >= 0

        # 验证阅读顺序
        order_indices = [elem.order_index for elem in elements]
        assert order_indices == list(range(len(elements))), "order_index should be consecutive"

        # 验证至少包含一些预期的元素类型
        element_types = {elem.type for elem in elements}
        assert "title" in element_types or "paragraph" in element_types


def test_parse_structured_elements_types():
    """测试结构化元素类型识别"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        _create_test_pdf(pdf_path)

        doc = fitz.open(pdf_path)
        elements = parse_structured_elements(doc, "paper_test_001", "single_column")
        doc.close()

        # 统计元素类型
        type_counts = {}
        for elem in elements:
            type_counts[elem.type] = type_counts.get(elem.type, 0) + 1

        # 应该至少有一些段落
        assert type_counts.get("paragraph", 0) > 0, "Should have at least some paragraphs"

