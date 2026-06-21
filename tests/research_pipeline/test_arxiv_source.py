"""
Tests for arXiv Source Adapter
"""

import pytest

from app.research_pipeline.schemas import PaperCandidate
from app.research_pipeline.sources.arxiv import ArxivSourceAdapter


class FakeArxivMCPAdapter:
    """Fake MCP adapter for testing (no network calls)."""

    def __init__(self, search_result: list[dict] | None = None, should_fail: bool = False):
        self.search_result = search_result or []
        self.should_fail = should_fail
        self.last_query = None
        self.last_max_results = None

    def search_papers(self, query: str, max_results: int = 10) -> list[dict]:
        """Fake search_papers that returns preset results."""
        self.last_query = query
        self.last_max_results = max_results

        if self.should_fail:
            raise RuntimeError("Simulated MCP adapter failure")

        return self.search_result


def test_search_returns_normalized_candidates():
    """Test that search returns normalized PaperCandidate objects."""
    raw_papers = [
        {
            "arxiv_id": "1706.03762",
            "title": "Attention Is All You Need",
            "authors": [{"name": "Ashish Vaswani"}, {"name": "Noam Shazeer"}],
            "published": "2017-06-12T17:57:34Z",
            "summary": "The dominant sequence transduction models...",
            "doi": "10.5555/3295222.3295349",
            "id": "http://arxiv.org/abs/1706.03762v5",
            "pdf_url": "http://arxiv.org/pdf/1706.03762v5",
        }
    ]

    fake_client = FakeArxivMCPAdapter(search_result=raw_papers)
    adapter = ArxivSourceAdapter(client=fake_client)

    candidates = adapter.search(query="transformers", max_results=10)

    assert len(candidates) == 1
    candidate = candidates[0]

    # Verify it's a PaperCandidate
    assert isinstance(candidate, PaperCandidate)

    # Verify field mapping
    assert candidate.paper_id == "1706.03762"
    assert candidate.source == "arxiv"
    assert candidate.title == "Attention Is All You Need"
    assert candidate.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert candidate.year == 2017
    assert candidate.abstract == "The dominant sequence transduction models..."
    assert candidate.arxiv_id == "1706.03762"
    assert candidate.doi == "10.5555/3295222.3295349"
    assert candidate.url == "http://arxiv.org/abs/1706.03762v5"
    assert candidate.pdf_url == "http://arxiv.org/pdf/1706.03762v5"


def test_search_with_missing_fields():
    """Test that search handles papers with missing optional fields."""
    raw_papers = [
        {
            "arxiv_id": "2024.12345",
            "title": "Some Paper",
            "authors": [],
            # Missing: published, summary, doi, id, pdf_url
        }
    ]

    fake_client = FakeArxivMCPAdapter(search_result=raw_papers)
    adapter = ArxivSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", max_results=5)

    assert len(candidates) == 1
    candidate = candidates[0]

    assert candidate.paper_id == "2024.12345"
    assert candidate.title == "Some Paper"
    assert candidate.authors == []
    assert candidate.year is None
    assert candidate.abstract is None
    assert candidate.doi is None
    assert candidate.url is None
    assert candidate.pdf_url is None


def test_search_empty_results():
    """Test that search returns empty list when no papers found."""
    fake_client = FakeArxivMCPAdapter(search_result=[])
    adapter = ArxivSourceAdapter(client=fake_client)

    candidates = adapter.search(query="nonexistent topic", max_results=10)

    assert candidates == []


def test_search_passes_parameters_to_client():
    """Test that search passes query and max_results to the underlying client."""
    fake_client = FakeArxivMCPAdapter(search_result=[])
    adapter = ArxivSourceAdapter(client=fake_client)

    adapter.search(query="machine learning", max_results=25)

    assert fake_client.last_query == "machine learning"
    assert fake_client.last_max_results == 25


def test_search_handles_client_exception():
    """Test that search handles client exceptions gracefully."""
    fake_client = FakeArxivMCPAdapter(should_fail=True)
    adapter = ArxivSourceAdapter(client=fake_client)

    with pytest.raises(RuntimeError, match="Simulated MCP adapter failure"):
        adapter.search(query="test", max_results=10)


def test_search_multiple_papers():
    """Test that search returns multiple normalized candidates."""
    raw_papers = [
        {
            "arxiv_id": "2020.00001",
            "title": "First Paper",
            "authors": [{"name": "Author One"}],
            "published": "2020-01-01T00:00:00Z",
            "pdf_url": "http://arxiv.org/pdf/2020.00001",
        },
        {
            "arxiv_id": "2021.00002",
            "title": "Second Paper",
            "authors": [{"name": "Author Two"}],
            "published": "2021-01-01T00:00:00Z",
            "pdf_url": "http://arxiv.org/pdf/2021.00002",
        },
        {
            "arxiv_id": "2022.00003",
            "title": "Third Paper",
            "authors": [{"name": "Author Three"}],
            "published": "2022-01-01T00:00:00Z",
            "pdf_url": "http://arxiv.org/pdf/2022.00003",
        },
    ]

    fake_client = FakeArxivMCPAdapter(search_result=raw_papers)
    adapter = ArxivSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", max_results=3)

    assert len(candidates) == 3
    assert candidates[0].paper_id == "2020.00001"
    assert candidates[1].paper_id == "2021.00002"
    assert candidates[2].paper_id == "2022.00003"


def test_search_with_year_extraction():
    """Test that search correctly extracts year from published date."""
    raw_papers = [
        {
            "arxiv_id": "1234.5678",
            "title": "Paper from 2019",
            "authors": [],
            "published": "2019-03-15T12:00:00Z",
        }
    ]

    fake_client = FakeArxivMCPAdapter(search_result=raw_papers)
    adapter = ArxivSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", max_results=1)

    assert len(candidates) == 1
    assert candidates[0].year == 2019


def test_search_with_invalid_year_format():
    """Test that search handles invalid published date format."""
    raw_papers = [
        {
            "arxiv_id": "1234.5678",
            "title": "Paper with Invalid Date",
            "authors": [],
            "published": "invalid-date",
        }
    ]

    fake_client = FakeArxivMCPAdapter(search_result=raw_papers)
    adapter = ArxivSourceAdapter(client=fake_client)

    candidates = adapter.search(query="test", max_results=1)

    assert len(candidates) == 1
    assert candidates[0].year is None


def test_search_with_no_client():
    """Test that search raises error when client is None."""
    adapter = ArxivSourceAdapter(client=None)

    with pytest.raises(RuntimeError, match="ArxivMCPAdapter client is not initialized"):
        adapter.search(query="test", max_results=10)
