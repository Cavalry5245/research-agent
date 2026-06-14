"""
Tests for chunk_parent_documents function.
"""

import pytest

from app.schemas import ParentDocument
from app.services.parent_chunker import chunk_parent_documents


class TestChunkParentDocuments:
    """Tests for chunk_parent_documents function."""

    def test_empty_parents_list(self):
        """Test with empty parents list."""
        chunks = chunk_parent_documents([])
        assert chunks == []

    def test_short_parent_one_chunk(self):
        """Test short parent document generates one chunk."""
        parent = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Introduction",
            content="This is a short introduction section.",
            page_range="1",
            element_type="section",
            element_ids=["elem_001"],
        )

        chunks = chunk_parent_documents([parent], chunk_size=500, chunk_overlap=100)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.parent_id == "parent_001_0001"
        assert chunk.paper_id == "paper_001"
        assert chunk.title == "Test Paper"
        assert chunk.section == "Introduction"
        assert chunk.section_path == "Introduction"
        assert chunk.page_range == "1"
        assert chunk.page_number == 1
        assert chunk.element_type == "section"
        assert chunk.content == "This is a short introduction section."
        assert chunk.context_header == "Test Paper | Introduction | p.1"
        assert "Test Paper | Introduction | p.1" in chunk.content_for_embedding
        assert "This is a short introduction section." in chunk.content_for_embedding

    def test_long_parent_multiple_chunks(self):
        """Test long parent document generates multiple overlapping chunks."""
        # Create a parent with content longer than chunk_size
        long_content = "A" * 600 + " " + "B" * 600

        parent = ParentDocument(
            parent_id="parent_001_0002",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Method",
            content=long_content,
            page_range="3-5",
            element_type="section",
            element_ids=["elem_010", "elem_011"],
        )

        chunks = chunk_parent_documents([parent], chunk_size=500, chunk_overlap=100)

        # Should generate multiple chunks
        assert len(chunks) > 1

        # All chunks should have parent_id
        for chunk in chunks:
            assert chunk.parent_id == "parent_001_0002"
            assert chunk.paper_id == "paper_001"
            assert chunk.section_path == "Method"
            assert chunk.page_range == "3-5"
            assert chunk.page_number == 3  # First page of range
            assert chunk.context_header is not None
            assert chunk.content_for_embedding is not None

        # Check overlap exists
        if len(chunks) >= 2:
            # chunk_end of first should be > chunk_start of second (overlap)
            assert chunks[0].chunk_end > chunks[1].chunk_start

    def test_chunk_ids_sequential(self):
        """Test chunk IDs are sequential across parents."""
        parent1 = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Introduction",
            content="A" * 300,
            page_range="1",
            element_type="section",
        )

        parent2 = ParentDocument(
            parent_id="parent_001_0002",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Method",
            content="B" * 300,
            page_range="2",
            element_type="section",
        )

        chunks = chunk_parent_documents([parent1, parent2])

        # Check chunk IDs are sequential
        assert chunks[0].chunk_id == "paper_001_chunk_0001"
        assert chunks[1].chunk_id == "paper_001_chunk_0002"

    def test_chunks_do_not_cross_parent_boundary(self):
        """Test chunks do not cross parent document boundaries."""
        parent1 = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Introduction",
            content="A" * 300,
            page_range="1",
            element_type="section",
        )

        parent2 = ParentDocument(
            parent_id="parent_001_0002",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Method",
            content="B" * 300,
            page_range="2",
            element_type="section",
        )

        chunks = chunk_parent_documents([parent1, parent2])

        # All chunks from parent1 should only contain "A"
        parent1_chunks = [c for c in chunks if c.parent_id == "parent_001_0001"]
        for chunk in parent1_chunks:
            assert "B" not in chunk.content

        # All chunks from parent2 should only contain "B"
        parent2_chunks = [c for c in chunks if c.parent_id == "parent_001_0002"]
        for chunk in parent2_chunks:
            assert "A" not in chunk.content

    def test_section_extracted_from_path(self):
        """Test section name is correctly extracted from section_path."""
        parent = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Method/Feature Extraction",
            content="Feature extraction method description.",
            page_range="3",
            element_type="section",
        )

        chunks = chunk_parent_documents([parent])

        assert len(chunks) == 1
        # Should extract last component of path
        assert chunks[0].section == "Feature Extraction"
        assert chunks[0].section_path == "Method/Feature Extraction"

    def test_page_range_parsing(self):
        """Test page_range is correctly parsed to page_number."""
        # Single page
        parent1 = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Introduction",
            content="This is the introduction content with enough text to pass min_chunk_chars.",
            page_range="5",
            element_type="section",
        )

        chunks1 = chunk_parent_documents([parent1])
        assert len(chunks1) > 0
        assert chunks1[0].page_number == 5

        # Page range
        parent2 = ParentDocument(
            parent_id="parent_001_0002",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Method",
            content="This is the method section with enough text to pass min_chunk_chars.",
            page_range="10-12",
            element_type="section",
        )

        chunks2 = chunk_parent_documents([parent2])
        assert len(chunks2) > 0
        assert chunks2[0].page_number == 10  # First page of range

    def test_context_header_format(self):
        """Test context_header has correct format."""
        parent = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Deep Learning Paper",
            section_path="Method/CNN Architecture",
            content="CNN architecture description.",
            page_range="5-7",
            element_type="section",
        )

        chunks = chunk_parent_documents([parent])

        expected_header = "Deep Learning Paper | Method/CNN Architecture | p.5-7"
        assert chunks[0].context_header == expected_header

    def test_content_for_embedding_includes_context(self):
        """Test content_for_embedding includes context_header."""
        parent = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Introduction",
            content="This is the introduction content.",
            page_range="1",
            element_type="section",
        )

        chunks = chunk_parent_documents([parent])

        embedding_content = chunks[0].content_for_embedding
        # Should contain context header
        assert "Test Paper | Introduction | p.1" in embedding_content
        # Should contain actual content
        assert "This is the introduction content." in embedding_content
        # Header should come before content
        header_pos = embedding_content.find("Test Paper")
        content_pos = embedding_content.find("This is the introduction")
        assert header_pos < content_pos

    def test_min_chunk_chars_respected(self):
        """Test chunks smaller than min_chunk_chars are filtered out."""
        parent = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Introduction",
            content="A" * 15,  # Less than default min_chunk_chars (20)
            page_range="1",
            element_type="section",
        )

        chunks = chunk_parent_documents([parent], min_chunk_chars=20)

        # Should not generate any chunks
        assert len(chunks) == 0

    def test_multiple_parents_different_types(self):
        """Test chunking multiple parents with different element types."""
        abstract = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Abstract",
            content="This is the abstract." * 10,
            page_range="1",
            element_type="abstract",
        )

        section = ParentDocument(
            parent_id="parent_001_0002",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Method",
            content="This is the method section." * 10,
            page_range="3-5",
            element_type="section",
        )

        table = ParentDocument(
            parent_id="parent_001_0003",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Results",
            content="Table data here." * 5,
            page_range="7",
            element_type="table",
        )

        chunks = chunk_parent_documents([abstract, section, table])

        # Should generate chunks from all parents
        assert len(chunks) >= 3

        # Each parent should have at least one chunk
        parent_ids = {c.parent_id for c in chunks}
        assert "parent_001_0001" in parent_ids
        assert "parent_001_0002" in parent_ids
        assert "parent_001_0003" in parent_ids

        # Check element types are preserved
        for chunk in chunks:
            if chunk.parent_id == "parent_001_0001":
                assert chunk.element_type == "abstract"
            elif chunk.parent_id == "parent_001_0002":
                assert chunk.element_type == "section"
            elif chunk.parent_id == "parent_001_0003":
                assert chunk.element_type == "table"

    def test_no_page_range_handled_gracefully(self):
        """Test parent without page_range is handled gracefully."""
        parent = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Introduction",
            content="Content without page range.",
            page_range=None,
            element_type="section",
        )

        chunks = chunk_parent_documents([parent])

        assert len(chunks) == 1
        assert chunks[0].page_range is None
        assert chunks[0].page_number is None
        assert "p.?" in chunks[0].context_header

    def test_chunk_start_end_positions(self):
        """Test chunk_start and chunk_end positions are correct."""
        content = "A" * 300 + "B" * 300 + "C" * 300

        parent = ParentDocument(
            parent_id="parent_001_0001",
            paper_id="paper_001",
            title="Test Paper",
            section_path="Method",
            content=content,
            page_range="2",
            element_type="section",
        )

        chunks = chunk_parent_documents([parent], chunk_size=500, chunk_overlap=100)

        # Check positions are within parent content bounds
        for chunk in chunks:
            assert 0 <= chunk.chunk_start < len(content)
            assert chunk.chunk_start < chunk.chunk_end <= len(content)
            # Verify content matches positions
            assert chunk.content == content[chunk.chunk_start:chunk.chunk_end].strip()
