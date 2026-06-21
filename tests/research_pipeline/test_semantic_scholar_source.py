"""
Tests for Semantic Scholar Source Adapter
"""

import pytest

from app.research_pipeline.schemas import PaperCandidate
from app.research_pipeline.sources.semantic_scholar import SemanticScholarSourceAdapter


class FakeSemanticScholarMCPAdapter:
    """Fake MCP adapter for testing (no network calls)."""

    def __init__(self, search_result: list[dict] | None = None, should_fail: bool = False):
        self.search_result = search_result or []
        self.should_fail = should_fail
        self.last_query = None
        self.last_limit = None

    def search_papers(self, query: str, limit: int = 10) -> list[dict]:
        """Fake search_papers that returns preset results."""
        self.last_query = query
        self.last_limit = limit

        if self.should_fail:
            raise RuntimeError("Simulated MCP adapter failure")

        return self.search_result


def test_search_returns_normalized_candidates():
    """Test that search returns normalized PaperCandidate objects."""
    raw_papers = [
        {
            "paperId": "abc123",
            "title": "Attention Is All You Need",
            "authors": [{"name": "Ashish Vaswani"}, {"name": "Noam Shazeer"}],
            "year": 2017,
            "venue": "NeurIPS",
            "abstract": "The dominant sequence transduction models...",
            "citationCount": 50000,
            "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762.pdf"},
            "externalIds": {"DOI": "10.5555/3295222.3295349", "ArXiv": "1706.03762"},
            "url": "https://www.semanticscholar.org/paper/abc123",
        }
    ]

    fake_client = FakeSemanticScholarMCPAdapter(search_result=raw_papers)
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    candidates = adapter.search(query="transformers", limit=10)

    assert len(candidates) == 1
    candidate = candidates[0]

    # Verify it's a PaperCandidate
    assert isinstance(candidate, PaperCandidate)

    # Verify field mapping
    assert candidate.paper_id == "abc123"
    assert candidate.source == "semantic_scholar"
    assert candidate.title == "Attention Is All You Need"
    assert candidate.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert candidate.year == 2017
    assert candidate.venue == "NeurIPS"
    assert candidate.abstract == "The dominant sequence transduction models..."
    assert candidate.citation_count == 50000
    assert candidate.pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"
    assert candidate.semantic_scholar_id == "abc123"
    assert candidate.doi == "10.5555/3295222.3295349"
    assert candidate.arxiv_id == "1706.03762"
    assert candidate.url == "https://www.semanticscholar.org/paper/abc123"


def test_search_with_missing_fields():
    """Test that search handles papers with missing optional fields."""
    raw_papers = [
        {
            "paperId": "xyz789",
            "title": "Some Paper",
            "authors": [],
            # Missing: year, venue, abstract, citationCount, openAccessPdf, externalIds, url
        }
    ]

    fake_client = FakeSemanticScholarMCPAdapter(search_result=raw_papers)
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", limit=5)

    assert len(candidates) == 1
    candidate = candidates[0]

    assert candidate.paper_id == "xyz789"
    assert candidate.title == "Some Paper"
    assert candidate.authors == []
    assert candidate.year is None
    assert candidate.venue is None
    assert candidate.abstract is None
    assert candidate.citation_count is None
    assert candidate.pdf_url is None
    assert candidate.doi is None
    assert candidate.arxiv_id is None
    assert candidate.url is None


def test_search_empty_results():
    """Test that search returns empty list when no papers found."""
    fake_client = FakeSemanticScholarMCPAdapter(search_result=[])
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    candidates = adapter.search(query="nonexistent topic", limit=10)

    assert candidates == []


def test_search_passes_parameters_to_client():
    """Test that search passes query and limit to the underlying client."""
    fake_client = FakeSemanticScholarMCPAdapter(search_result=[])
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    adapter.search(query="machine learning", limit=25)

    assert fake_client.last_query == "machine learning"
    assert fake_client.last_limit == 25


def test_search_handles_client_exception():
    """Test that search handles client exceptions gracefully."""
    fake_client = FakeSemanticScholarMCPAdapter(should_fail=True)
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    with pytest.raises(RuntimeError, match="Simulated MCP adapter failure"):
        adapter.search(query="test", limit=10)


def test_search_multiple_papers():
    """Test that search returns multiple normalized candidates."""
    raw_papers = [
        {
            "paperId": "paper1",
            "title": "First Paper",
            "authors": [{"name": "Author One"}],
            "year": 2020,
            "citationCount": 100,
        },
        {
            "paperId": "paper2",
            "title": "Second Paper",
            "authors": [{"name": "Author Two"}],
            "year": 2021,
            "citationCount": 200,
        },
        {
            "paperId": "paper3",
            "title": "Third Paper",
            "authors": [{"name": "Author Three"}],
            "year": 2022,
            "citationCount": 300,
        },
    ]

    fake_client = FakeSemanticScholarMCPAdapter(search_result=raw_papers)
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", limit=3)

    assert len(candidates) == 3
    assert candidates[0].paper_id == "paper1"
    assert candidates[1].paper_id == "paper2"
    assert candidates[2].paper_id == "paper3"


def test_search_with_null_openaccesspdf():
    """Test that search handles null openAccessPdf field."""
    raw_papers = [
        {
            "paperId": "paper1",
            "title": "Paper with No PDF",
            "authors": [],
            "openAccessPdf": None,
        }
    ]

    fake_client = FakeSemanticScholarMCPAdapter(search_result=raw_papers)
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", limit=1)

    assert len(candidates) == 1
    assert candidates[0].pdf_url is None


def test_search_with_empty_openaccesspdf():
    """Test that search handles empty openAccessPdf dict."""
    raw_papers = [
        {
            "paperId": "paper1",
            "title": "Paper with Empty PDF",
            "authors": [],
            "openAccessPdf": {},
        }
    ]

    fake_client = FakeSemanticScholarMCPAdapter(search_result=raw_papers)
    adapter = SemanticScholarSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", limit=1)

    assert len(candidates) == 1
    assert candidates[0].pdf_url is None
