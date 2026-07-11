"""
Integration tests for section tree building with real PDF files (Task 2.3).
"""

import os

import fitz
import pytest

from app.services.pdf_parser import (
    build_section_tree,
    generate_pdf_profile,
    parse_structured_elements,
)


@pytest.fixture
def sample_pdf_path():
    """Find a sample PDF for testing."""
    # Check if test PDF exists
    test_pdf = "tests/data/sample.pdf"
    if os.path.exists(test_pdf):
        return test_pdf

    # Check upload directory — require a text-based PDF that passes profiling,
    # since the shared storage dir can accumulate stub/fake PDFs from other tests
    # (fail to open) or scanned/image PDFs (open but have no extractable text).
    upload_dir = "app/storage/papers"
    if os.path.exists(upload_dir):
        pdfs = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
        for name in pdfs:
            candidate = os.path.join(upload_dir, name)
            try:
                doc = fitz.open(candidate)
                generate_pdf_profile(doc, "fixture_probe")
                doc.close()
            except Exception:
                continue
            return candidate

    pytest.skip("No valid text-based sample PDF found for integration testing")


def test_full_pipeline_with_real_pdf(sample_pdf_path):
    """Test the full pipeline with a real PDF file."""
    paper_id = "test_integration_001"

    # Open PDF
    doc = fitz.open(sample_pdf_path)

    try:
        # Step 1: Generate PDF profile
        profile = generate_pdf_profile(doc, paper_id)
        assert profile.paper_id == paper_id
        assert profile.is_text_pdf is True
        assert profile.layout_type in ["single_column", "double_column", "unknown"]

        print(f"\nPDF Profile:")
        print(f"  Pages: {profile.page_count}")
        print(f"  Layout: {profile.layout_type}")
        print(f"  Text density: {profile.text_density}")
        print(f"  Has tables: {profile.has_tables}")
        print(f"  Has figures: {profile.has_figures}")
        print(f"  References start page: {profile.reference_page_start}")

        # Step 2: Parse structured elements
        elements = parse_structured_elements(doc, paper_id, profile.layout_type)
        assert len(elements) > 0

        print(f"\nParsed {len(elements)} elements")

        # Verify all elements have required fields
        for elem in elements:
            assert elem.element_id.startswith(paper_id)
            assert elem.paper_id == paper_id
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
            assert elem.page_number > 0
            assert elem.order_index >= 0

        # Step 3: Build section tree
        elements = build_section_tree(elements)

        # Collect section statistics
        section_paths = set()
        sections_by_level = {1: [], 2: [], 3: []}
        in_references_count = 0

        for elem in elements:
            if elem.section_path:
                section_paths.add(elem.section_path)

                # Determine level by counting '/'
                level = elem.section_path.count("/") + 1
                if elem.type in ["heading", "title"] and level <= 3:
                    sections_by_level[level].append(elem.section_path)

            if elem.metadata.get("in_references"):
                in_references_count += 1

        print(f"\nSection Tree Statistics:")
        print(f"  Total unique sections: {len(section_paths)}")
        print(f"  Level 1 sections: {len(set(sections_by_level[1]))}")
        print(f"  Level 2 sections: {len(set(sections_by_level[2]))}")
        print(f"  Level 3 sections: {len(set(sections_by_level[3]))}")
        print(f"  Elements in References: {in_references_count}")

        # Print sample sections
        print(f"\nSample section paths:")
        for path in sorted(list(section_paths))[:10]:
            print(f"  - {path}")

        # Assertions
        assert len(section_paths) > 0, "Should identify at least one section"

        # Verify section_path is set for most elements
        elements_with_section = [e for e in elements if e.section_path is not None]
        coverage = len(elements_with_section) / len(elements)
        print(f"\nSection coverage: {coverage:.1%}")
        assert coverage > 0.5, "At least 50% of elements should have section_path"

        # Verify References marking if References section exists
        references_elements = [
            e for e in elements if e.metadata.get("in_references") is True
        ]
        if references_elements:
            print(f"\nReferences section detected with {len(references_elements)} elements")
            # All references elements should come after non-references
            ref_indices = [e.order_index for e in references_elements]
            non_ref_indices = [
                e.order_index
                for e in elements
                if not e.metadata.get("in_references")
            ]
            if non_ref_indices:
                assert min(ref_indices) > max(non_ref_indices), \
                    "References should come after main content"

        # Print element type distribution
        type_counts = {}
        for elem in elements:
            type_counts[elem.type] = type_counts.get(elem.type, 0) + 1

        print(f"\nElement type distribution:")
        for elem_type, count in sorted(type_counts.items()):
            print(f"  {elem_type}: {count}")

    finally:
        doc.close()


def test_section_path_format(sample_pdf_path):
    """Test that section paths follow the correct format."""
    paper_id = "test_format_001"
    doc = fitz.open(sample_pdf_path)

    try:
        profile = generate_pdf_profile(doc, paper_id)
        elements = parse_structured_elements(doc, paper_id, profile.layout_type)
        elements = build_section_tree(elements)

        for elem in elements:
            if elem.section_path:
                # Section path should not start or end with '/'
                assert not elem.section_path.startswith("/")
                assert not elem.section_path.endswith("/")

                # Should not have consecutive '/'
                assert "//" not in elem.section_path

                # Should have at most 3 levels (2 slashes)
                assert elem.section_path.count("/") <= 2

    finally:
        doc.close()


def test_heading_elements_have_section_path(sample_pdf_path):
    """Test that all heading elements have section_path assigned."""
    paper_id = "test_headings_001"
    doc = fitz.open(sample_pdf_path)

    try:
        profile = generate_pdf_profile(doc, paper_id)
        elements = parse_structured_elements(doc, paper_id, profile.layout_type)
        elements = build_section_tree(elements)

        headings = [e for e in elements if e.type in ["heading", "title"]]

        if headings:
            # All headings should have section_path
            headings_with_path = [h for h in headings if h.section_path]
            coverage = len(headings_with_path) / len(headings)

            print(f"\nHeading section path coverage: {coverage:.1%}")
            assert coverage >= 0.9, "At least 90% of headings should have section_path"

    finally:
        doc.close()


def test_section_inheritance(sample_pdf_path):
    """Test that non-heading elements inherit section paths correctly."""
    paper_id = "test_inheritance_001"
    doc = fitz.open(sample_pdf_path)

    try:
        profile = generate_pdf_profile(doc, paper_id)
        elements = parse_structured_elements(doc, paper_id, profile.layout_type)
        elements = build_section_tree(elements)

        # Find first heading
        first_heading_idx = None
        for i, elem in enumerate(elements):
            if elem.type == "heading":
                first_heading_idx = i
                break

        if first_heading_idx is not None:
            first_heading = elements[first_heading_idx]

            # Elements after this heading should have the same or deeper section path
            for i in range(first_heading_idx + 1, min(first_heading_idx + 10, len(elements))):
                elem = elements[i]

                if elem.type not in ["heading", "title"] and elem.section_path:
                    # Non-heading should have section path starting with the heading's path
                    # or a new section (if another heading appears)
                    if not any(
                        e.type in ["heading", "title"]
                        for e in elements[first_heading_idx + 1 : i]
                    ):
                        # No heading in between, should inherit
                        assert elem.section_path.startswith(
                            first_heading.section_path.split("/")[0]
                        ), f"Element {elem.element_id} should inherit section from heading"

    finally:
        doc.close()
