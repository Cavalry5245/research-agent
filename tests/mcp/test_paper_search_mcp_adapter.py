"""Tests for the paper-search-mcp adapter, normalizer, and server lifecycle."""

from __future__ import annotations

import pytest

from app.mcp.client_manager import MCPClientManager
from app.mcp.paper_normalizer import (
    dedupe_papers,
    extract_doi,
    normalize_paper,
)
from app.mcp.schemas import MCPServerConfig, MCPToolResult, Paper
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.paper_search_mcp_adapter import (
    DEFAULT_SOURCES,
    PaperSearchMCPAdapter,
)


# ---------------------------------------------------------------------------
# extract_doi
# ---------------------------------------------------------------------------


def test_extract_doi_from_text():
    assert extract_doi("see https://doi.org/10.1038/nature12373 for details") == "10.1038/nature12373"


def test_extract_doi_strips_trailing_punctuation():
    assert extract_doi("ref 10.1000/xyz.123.) end") == "10.1000/xyz.123"


def test_extract_doi_returns_empty_when_absent():
    assert extract_doi("no doi here") == ""
    assert extract_doi("") == ""


# ---------------------------------------------------------------------------
# normalize_paper — three upstream shapes
# ---------------------------------------------------------------------------


def test_normalize_paper_search_mcp_to_dict_shape():
    """paper-search-mcp Paper.to_dict(): authors joined by '; '."""
    raw = {
        "paper_id": "2106.15928",
        "title": "Retrieval-Augmented Generation",
        "authors": "Lewis; Perez; Piktus",
        "abstract": "We introduce RAG. doi: 10.5555/rag.1234",
        "doi": "",
        "published_date": "2021-06-30T00:00:00",
        "pdf_url": "https://arxiv.org/pdf/2106.15928",
        "url": "https://arxiv.org/abs/2106.15928",
        "source": "arxiv",
        "categories": "cs.CL; cs.IR",
        "citations": 42,
    }
    paper = normalize_paper(raw)
    assert isinstance(paper, Paper)
    assert paper.paper_id == "2106.15928"
    assert paper.authors == ["Lewis", "Perez", "Piktus"]
    assert paper.doi == "10.5555/rag.1234"  # backfilled from abstract
    assert paper.published_date == "2021-06-30T00:00:00"
    assert paper.citation_count == 42
    assert paper.source == "arxiv"
    assert paper.extra["categories"] == ["cs.CL", "cs.IR"]


def test_normalize_local_arxiv_shape():
    """The project's minimal_arxiv_server output: {id, authors: list, published}."""
    raw = {
        "id": "2106.15928",
        "title": "RAG",
        "authors": ["Lewis", "Perez"],
        "abstract": "Abstract text",
        "url": "https://arxiv.org/abs/2106.15928",
        "pdf_url": "https://arxiv.org/pdf/2106.15928",
        "published": "2021-06-30T00:00:00Z",
    }
    paper = normalize_paper(raw, source_hint="arxiv")
    assert paper.paper_id == "2106.15928"
    assert paper.authors == ["Lewis", "Perez"]
    assert paper.published_date == "2021-06-30T00:00:00Z"
    assert paper.source == "arxiv"


def test_normalize_local_semantic_scholar_shape():
    """Raw Semantic Scholar item: {paperId, authors: list[dict], openAccessPdf}."""
    raw = {
        "paperId": "abc123",
        "title": "Attention Is All You Need",
        "abstract": "We propose a new architecture.",
        "year": 2017,
        "citationCount": 9001,
        "referenceCount": 40,
        "url": "https://example.com/abc123",
        "authors": [
            {"authorId": "1", "name": "Vaswani"},
            {"authorId": "2", "name": "Shazeer"},
        ],
        "openAccessPdf": {"url": "https://example.com/abc123.pdf"},
        "venue": "NeurIPS",
    }
    paper = normalize_paper(raw, source_hint="semantic")
    assert paper.paper_id == "abc123"
    assert paper.authors == ["Vaswani", "Shazeer"]
    assert paper.pdf_url == "https://example.com/abc123.pdf"
    assert paper.year == 2017
    assert paper.citation_count == 9001
    assert paper.source == "semantic"
    assert paper.extra["venue"] == "NeurIPS"
    assert paper.extra["reference_count"] == 40


def test_normalize_paper_handles_non_dict():
    paper = normalize_paper("not a dict", source_hint="x")  # type: ignore[arg-type]
    assert paper.source == "x"
    assert paper.authors == []


# ---------------------------------------------------------------------------
# dedupe_papers
# ---------------------------------------------------------------------------


def test_dedupe_by_doi():
    a = normalize_paper({"paper_id": "a", "title": "A", "doi": "10.1/x", "source": "arxiv"})
    b = normalize_paper({"paper_id": "b", "title": "A (copy)", "doi": "10.1/X", "source": "semantic"})
    assert dedupe_papers([a, b]) == [a]


def test_dedupe_by_title_and_authors_when_no_doi():
    a = normalize_paper({"paper_id": "a", "title": "Same Title", "authors": ["X", "Y"]})
    b = normalize_paper({"paper_id": "b", "title": "same title", "authors": ["x", "y"]})
    assert dedupe_papers([a, b]) == [a]


def test_dedupe_keeps_distinct_papers():
    a = normalize_paper({"paper_id": "a", "title": "One", "doi": "10.1/a"})
    b = normalize_paper({"paper_id": "b", "title": "Two", "doi": "10.1/b"})
    assert len(dedupe_papers([a, b])) == 2


# ---------------------------------------------------------------------------
# Adapter — search_papers (FakeProxy, no real server)
# ---------------------------------------------------------------------------


def _success_result(result, server="paper-search", tool="search_papers"):
    return MCPToolResult(
        status="success",
        result=result,
        duration_ms=1.0,
        server_name=server,
        tool_name=tool,
    )


def test_adapter_search_papers_normalizes_and_dedupes():
    captured = {}

    class FakeProxy:
        def call_tool(self, call):
            captured["call"] = call
            return _success_result(
                {
                    "papers": [
                        # paper-search-mcp shape, DOI 10.1/x
                        {
                            "paper_id": "a",
                            "title": "A",
                            "authors": "Lewis; Perez",
                            "doi": "10.1/x",
                            "source": "arxiv",
                        },
                        # local arxiv shape, same DOI → should dedupe
                        {
                            "id": "b",
                            "title": "A duplicate",
                            "authors": ["Lewis"],
                            "doi": "10.1/x",
                        },
                        # distinct paper
                        {
                            "paper_id": "c",
                            "title": "C",
                            "authors": "Foo",
                            "doi": "10.1/c",
                            "source": "openalex",
                        },
                    ],
                    "total": 3,
                }
            )

    adapter = PaperSearchMCPAdapter(FakeProxy())
    papers = adapter.search_papers("rag", max_results_per_source=5, year="2021")

    assert captured["call"].server_name == "paper-search"
    assert captured["call"].tool_name == "search_papers"
    assert captured["call"].arguments["query"] == "rag"
    assert captured["call"].arguments["max_results_per_source"] == 5
    assert captured["call"].arguments["sources"] == DEFAULT_SOURCES
    assert captured["call"].arguments["year"] == "2021"

    # dedupe collapses the two 10.1/x entries → 2 papers
    assert len(papers) == 2
    assert all(isinstance(p, Paper) for p in papers)
    assert papers[0].authors == ["Lewis", "Perez"]  # authors normalized from str


def test_adapter_search_papers_returns_empty_on_error():
    class FakeProxy:
        def call_tool(self, call):
            return MCPToolResult(
                status="error",
                result=None,
                error="boom",
                duration_ms=1.0,
                server_name="paper-search",
                tool_name="search_papers",
            )

    adapter = PaperSearchMCPAdapter(FakeProxy())
    assert adapter.search_papers("anything") == []


def test_adapter_search_papers_default_sources_when_not_specified():
    """When sources arg absent, adapter passes its DEFAULT_SOURCES."""
    captured = {}

    class FakeProxy:
        def call_tool(self, call):
            captured["args"] = call.arguments
            return _success_result({"papers": []})

    adapter = PaperSearchMCPAdapter(FakeProxy())
    adapter.search_papers("q")
    assert captured["args"]["sources"] == DEFAULT_SOURCES


# ---------------------------------------------------------------------------
# Adapter — download (FakeProxy)
# ---------------------------------------------------------------------------


def test_adapter_download_passes_scihub_false_and_returns_path():
    captured = {}

    class FakeProxy:
        def call_tool(self, call):
            captured["call"] = call
            return _success_result(
                "/tmp/downloads/arxiv_2106.15928.pdf",
                tool="download_with_fallback",
            )

    adapter = PaperSearchMCPAdapter(FakeProxy())
    path = adapter.download(
        paper_id="2106.15928", source="arxiv", doi="10.1/x", title="RAG"
    )

    assert path == "/tmp/downloads/arxiv_2106.15928.pdf"
    args = captured["call"].arguments
    assert args["source"] == "arxiv"
    assert args["paper_id"] == "2106.15928"
    assert args["doi"] == "10.1/x"
    assert args["title"] == "RAG"
    assert args["use_scihub"] is False  # Sci-Hub never used


def test_adapter_download_returns_error_message_on_failure():
    class FakeProxy:
        def call_tool(self, call):
            return MCPToolResult(
                status="error",
                result=None,
                error="network down",
                duration_ms=1.0,
                server_name="paper-search",
                tool_name="download_with_fallback",
            )

    adapter = PaperSearchMCPAdapter(FakeProxy())
    msg = adapter.download(paper_id="x", source="arxiv")
    assert "download failed" in msg
    assert "network down" in msg


# ---------------------------------------------------------------------------
# Server lifecycle smoke test (skipped if paper_search_mcp is not importable)
# ---------------------------------------------------------------------------

_PAPER_SEARCH_IMPORTABLE = True
try:
    import paper_search_mcp  # noqa: F401
except Exception:  # pragma: no cover - depends on optional install
    _PAPER_SEARCH_IMPORTABLE = False


@pytest.mark.skipif(
    not _PAPER_SEARCH_IMPORTABLE,
    reason="paper-search-mcp not installed; run `pip install paper-search-mcp`",
)
def test_paper_search_mcp_server_exposes_expected_tools():
    manager = MCPClientManager()
    # Launch via the project's thin launcher (app.mcp.paper_search_server),
    # mirroring the `python -m app.mcp.minimal_*_server` pattern. This avoids
    # depending on a PATH-resident console script (0.1.x ships none).
    server_config = MCPServerConfig(
        name="paper-search",
        command=["python", "-m", "app.mcp.paper_search_server"],
    )
    manager.start_server(server_config)
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "search_papers" in tools["paper-search"]
    assert "download_with_fallback" in tools["paper-search"]
