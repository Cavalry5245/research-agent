"""
Unit tests for section tree building functionality (Task 2.3).
"""

import pytest

from app.schemas import DocumentElement
from app.services.pdf_parser import _detect_heading_level, build_section_tree


class TestDetectHeadingLevel:
    """Tests for _detect_heading_level() function."""

    def test_level_1_numbered(self):
        """Test level 1 detection with numbered headings."""
        # Test "1. Introduction"
        elem = DocumentElement(
            element_id="test_001",
            paper_id="paper_001",
            type="heading",
            text="1. Introduction",
            page_number=1,
            order_index=0,
        )
        assert _detect_heading_level(elem) == 1

        # Test "2 Method"
        elem.text = "2 Method"
        assert _detect_heading_level(elem) == 1

        # Test "I. Background"
        elem.text = "I. Background"
        assert _detect_heading_level(elem) == 1

    def test_level_1_keywords(self):
        """Test level 1 detection with keyword matching."""
        elem = DocumentElement(
            element_id="test_002",
            paper_id="paper_001",
            type="heading",
            text="Abstract",
            page_number=1,
            order_index=0,
        )
        assert _detect_heading_level(elem) == 1

        # Test different keywords
        keywords = [
            "Introduction",
            "Related Work",
            "Methodology",
            "Experiments",
            "Results",
            "Discussion",
            "Conclusion",
            "References",
        ]
        for kw in keywords:
            elem.text = kw
            assert _detect_heading_level(elem) == 1, f"Failed for keyword: {kw}"

    def test_level_1_numbered_keywords(self):
        """Test level 1 with numbered keywords."""
        elem = DocumentElement(
            element_id="test_003",
            paper_id="paper_001",
            type="heading",
            text="1. Introduction",
            page_number=1,
            order_index=0,
        )
        assert _detect_heading_level(elem) == 1

        elem.text = "3) Experiments"
        assert _detect_heading_level(elem) == 1

    def test_level_2_numbered(self):
        """Test level 2 detection with numbered headings."""
        elem = DocumentElement(
            element_id="test_004",
            paper_id="paper_001",
            type="heading",
            text="1.1 Background",
            page_number=1,
            order_index=0,
        )
        assert _detect_heading_level(elem) == 2

        elem.text = "2.3 Feature Extraction"
        assert _detect_heading_level(elem) == 2

    def test_level_3_numbered(self):
        """Test level 3 detection with numbered headings."""
        elem = DocumentElement(
            element_id="test_005",
            paper_id="paper_001",
            type="heading",
            text="1.1.1 Deep Learning",
            page_number=1,
            order_index=0,
        )
        assert _detect_heading_level(elem) == 3

        elem.text = "2.1.3 CNN Architecture"
        assert _detect_heading_level(elem) == 3

    def test_default_level_2(self):
        """Test that unknown headings default to level 2."""
        elem = DocumentElement(
            element_id="test_006",
            paper_id="paper_001",
            type="heading",
            text="Some Custom Section",
            page_number=1,
            order_index=0,
        )
        assert _detect_heading_level(elem) == 2


class TestBuildSectionTree:
    """Tests for build_section_tree() function."""

    def test_simple_hierarchy(self):
        """Test simple section hierarchy."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="Introduction",
                page_number=1,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="This is introduction text.",
                page_number=1,
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="heading",
                text="1.1 Motivation",
                page_number=1,
                order_index=2,
            ),
            DocumentElement(
                element_id="elem_004",
                paper_id="paper_001",
                type="paragraph",
                text="Motivation text here.",
                page_number=1,
                order_index=3,
            ),
        ]

        result = build_section_tree(elements)

        # Check section paths
        assert result[0].section_path == "Introduction"
        assert result[1].section_path == "Introduction"
        assert result[2].section_path == "Introduction/1.1 Motivation"
        assert result[3].section_path == "Introduction/1.1 Motivation"

    def test_three_level_hierarchy(self):
        """Test three-level section hierarchy."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="Method",
                page_number=2,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="heading",
                text="2.1 Feature Extraction",
                page_number=2,
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="heading",
                text="2.1.1 CNN Architecture",
                page_number=2,
                order_index=2,
            ),
            DocumentElement(
                element_id="elem_004",
                paper_id="paper_001",
                type="paragraph",
                text="CNN details.",
                page_number=2,
                order_index=3,
            ),
        ]

        result = build_section_tree(elements)

        assert result[0].section_path == "Method"
        assert result[1].section_path == "Method/2.1 Feature Extraction"
        assert result[2].section_path == "Method/2.1 Feature Extraction/2.1.1 CNN Architecture"
        assert result[3].section_path == "Method/2.1 Feature Extraction/2.1.1 CNN Architecture"

    def test_references_marking(self):
        """Test that References section is marked in metadata."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="Conclusion",
                page_number=5,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Conclusion text.",
                page_number=5,
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="heading",
                text="References",
                page_number=6,
                order_index=2,
            ),
            DocumentElement(
                element_id="elem_004",
                paper_id="paper_001",
                type="reference",
                text="[1] Smith et al., 2020",
                page_number=6,
                order_index=3,
            ),
        ]

        result = build_section_tree(elements)

        # Elements before References should not be marked
        assert result[0].metadata.get("in_references") is None
        assert result[1].metadata.get("in_references") is None

        # References heading and content should be marked
        assert result[2].metadata.get("in_references") is True
        assert result[3].metadata.get("in_references") is True

    def test_references_with_numbering(self):
        """Test References detection with numbering."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="6. References",
                page_number=6,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="reference",
                text="[1] Reference text",
                page_number=6,
                order_index=1,
            ),
        ]

        result = build_section_tree(elements)

        assert result[0].metadata.get("in_references") is True
        assert result[1].metadata.get("in_references") is True

    def test_no_headings(self):
        """Test handling of documents with no headings."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Some text without headings.",
                page_number=1,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="More text.",
                page_number=1,
                order_index=1,
            ),
        ]

        result = build_section_tree(elements)

        # Elements before any heading should have None section_path
        assert result[0].section_path is None
        assert result[1].section_path is None

    def test_title_before_heading(self):
        """Test title elements before first heading."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="title",
                text="Paper Title Here",
                page_number=1,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Author names",
                page_number=1,
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="heading",
                text="Abstract",
                page_number=1,
                order_index=2,
            ),
            DocumentElement(
                element_id="elem_004",
                paper_id="paper_001",
                type="paragraph",
                text="Abstract content.",
                page_number=1,
                order_index=3,
            ),
        ]

        result = build_section_tree(elements)

        # Title should set its own section path
        assert result[0].section_path == "Paper Title Here"
        # Paragraph after title inherits title section
        assert result[1].section_path == "Paper Title Here"
        # Abstract heading
        assert result[2].section_path == "Abstract"
        # Abstract content
        assert result[3].section_path == "Abstract"

    def test_multiple_sections(self):
        """Test multiple level-1 sections."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="Introduction",
                page_number=1,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Intro text.",
                page_number=1,
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="heading",
                text="Method",
                page_number=2,
                order_index=2,
            ),
            DocumentElement(
                element_id="elem_004",
                paper_id="paper_001",
                type="paragraph",
                text="Method text.",
                page_number=2,
                order_index=3,
            ),
            DocumentElement(
                element_id="elem_005",
                paper_id="paper_001",
                type="heading",
                text="Experiments",
                page_number=3,
                order_index=4,
            ),
            DocumentElement(
                element_id="elem_006",
                paper_id="paper_001",
                type="paragraph",
                text="Experiment text.",
                page_number=3,
                order_index=5,
            ),
        ]

        result = build_section_tree(elements)

        assert result[0].section_path == "Introduction"
        assert result[1].section_path == "Introduction"
        assert result[2].section_path == "Method"
        assert result[3].section_path == "Method"
        assert result[4].section_path == "Experiments"
        assert result[5].section_path == "Experiments"

    def test_edge_case_level2_first(self):
        """Test edge case: document starts with level 2 heading."""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="1.1 Background",
                page_number=1,
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Background text.",
                page_number=1,
                order_index=1,
            ),
        ]

        result = build_section_tree(elements)

        # Should still set section path even without parent
        assert result[0].section_path == "1.1 Background"
        assert result[1].section_path == "1.1 Background"
