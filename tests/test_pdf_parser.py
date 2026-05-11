import json
import os
import sys
import tempfile

import fitz
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.pdf_parser import parse_pdf, save_parse_result, generate_paper_id
from app.schemas import PaperParseResult


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
