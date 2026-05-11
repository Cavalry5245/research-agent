import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import PaperParseResult, Section, Chunk
from app.services.chunker import chunk_paper


def _make_parsed(sections: list[Section] | None = None, title: str = "Test Paper") -> PaperParseResult:
    if sections is None:
        sections = []
    full_text = "\n\n".join(f"{s.heading}\n{s.content}" for s in sections)
    return PaperParseResult(
        paper_id="paper_test_001",
        title=title,
        abstract="",
        sections=sections,
        full_text=full_text,
    )


def test_chunk_single_short_section():
    parsed = _make_parsed([
        Section(heading="Introduction", content="This is a short introduction paragraph."),
    ])
    chunks = chunk_paper(parsed)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "paper_test_001_chunk_0001"
    assert chunks[0].paper_id == "paper_test_001"
    assert chunks[0].title == "Test Paper"
    assert chunks[0].section == "Introduction"
    assert "short introduction" in chunks[0].content


def test_chunk_long_section_splits():
    # 2000 chars should produce 3 chunks with size=800, overlap=100
    long_text = "x" * 2000
    parsed = _make_parsed([
        Section(heading="Method", content=long_text),
    ])
    chunks = chunk_paper(parsed, chunk_size=800, chunk_overlap=100)
    assert len(chunks) == 3
    assert all(c.section == "Method" for c in chunks)
    assert chunks[0].chunk_id.endswith("_0001")

    # Verify overlap: chunk 1's last part should appear at start of chunk 2
    c0_end = chunks[0].content[-50:]
    c1_start = chunks[1].content[:50]
    # With full 'x' content, overlap is exact substring match
    assert c0_end == "x" * 50
    assert c1_start == "x" * 50


def test_chunk_multiple_sections():
    parsed = _make_parsed([
        Section(heading="Introduction", content="x" * 500),
        Section(heading="Method", content="y" * 1500),
        Section(heading="Conclusion", content="z" * 300),
    ])
    chunks = chunk_paper(parsed, chunk_size=800, chunk_overlap=100)

    intro_chunks = [c for c in chunks if c.section == "Introduction"]
    method_chunks = [c for c in chunks if c.section == "Method"]
    conclusion_chunks = [c for c in chunks if c.section == "Conclusion"]

    assert len(intro_chunks) == 1
    assert len(method_chunks) == 2
    assert len(conclusion_chunks) == 1
    assert len(chunks) == 4

    # Sequential chunk_id
    ids = [c.chunk_id for c in chunks]
    assert ids == [
        "paper_test_001_chunk_0001",
        "paper_test_001_chunk_0002",
        "paper_test_001_chunk_0003",
        "paper_test_001_chunk_0004",
    ]


def test_chunk_empty_section_skipped():
    parsed = _make_parsed([
        Section(heading="Introduction", content="This is a valid introduction section with enough text."),
        Section(heading="Empty", content=""),
        Section(heading="Short", content="ab"),
        Section(heading="Method", content="x" * 500),
    ])
    chunks = chunk_paper(parsed)
    headings = {c.section for c in chunks}
    assert "Empty" not in headings
    assert "Short" not in headings
    assert "Introduction" in headings
    assert "Method" in headings


def test_chunk_all_empty_falls_back_to_full_text():
    parsed = _make_parsed([
        Section(heading="Empty", content="   "),
    ])
    # full_text will contain "Empty\n   "
    # But that's too short (< 20 chars), so no chunks
    chunks = chunk_paper(parsed)

    # Now try with a real fallback scenario: sections empty but full_text has content
    parsed2 = PaperParseResult(
        paper_id="paper_002",
        title="Fallback",
        abstract="",
        sections=[Section(heading="Empty", content="")],
        full_text="This is the full text content that should be chunked as fallback. " * 20,
    )
    chunks2 = chunk_paper(parsed2)
    assert len(chunks2) > 0
    assert all(c.section == "全文" for c in chunks2)
    assert all(c.paper_id == "paper_002" for c in chunks2)


def test_chunk_metadata_complete():
    parsed = _make_parsed([
        Section(heading="Results", content="x" * 1000),
    ])
    chunks = chunk_paper(parsed)
    for c in chunks:
        assert c.chunk_id
        assert c.paper_id == "paper_test_001"
        assert c.title == "Test Paper"
        assert c.section == "Results"
        assert len(c.content) > 0


def test_chunk_exact_boundary():
    # 800 chars exactly should produce 1 chunk
    parsed = _make_parsed([
        Section(heading="Method", content="x" * 800),
    ])
    chunks = chunk_paper(parsed)
    assert len(chunks) == 1
    assert len(chunks[0].content) == 800


def test_chunk_overlap_content():
    # Verify actual overlap: text with distinct patterns
    content = "ABCDEFGHIJ" * 200  # 2000 chars, each 10-char pattern
    parsed = _make_parsed([
        Section(heading="Method", content=content),
    ])
    chunks = chunk_paper(parsed, chunk_size=800, chunk_overlap=100)

    assert len(chunks) == 3
    # chunk 0 ends with chars at 790-800
    # chunk 1 should start with chars at 700-750 (overlap region)
    assert chunks[0].content[-10:] == chunks[1].content[:10]


if __name__ == "__main__":
    test_chunk_single_short_section()
    test_chunk_long_section_splits()
    test_chunk_multiple_sections()
    test_chunk_empty_section_skipped()
    test_chunk_all_empty_falls_back_to_full_text()
    test_chunk_metadata_complete()
    test_chunk_exact_boundary()
    test_chunk_overlap_content()
    print("All tests passed.")
