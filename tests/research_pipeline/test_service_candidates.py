"""
Tests for ResearchPipelineService candidate visibility

Verifies that candidates written by RetrieverAgent are visible through
the service layer and API responses.
"""

import pytest
from datetime import datetime

from app.research_pipeline.service import ResearchPipelineService
from app.research_pipeline import store
from app.research_pipeline.schemas import ResearchRunCreateRequest, PaperCandidate


def test_service_get_run_detail_includes_candidates(tmp_path):
    """Service.get_run_detail should include candidates from store."""
    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    # Create run
    run_id = store.create_run(
        db_path=db_path,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Add candidates via store
    candidate_1 = PaperCandidate(
        paper_id="paper_1",
        source="semantic_scholar",
        title="Attention Is All You Need",
        authors=["Vaswani", "Shazeer"],
        year=2017,
        semantic_scholar_id="ss_1",
        citation_count=50000,
    )
    candidate_2 = PaperCandidate(
        paper_id="paper_2",
        source="arxiv",
        title="BERT: Pre-training of Deep Bidirectional Transformers",
        authors=["Devlin"],
        year=2018,
        arxiv_id="1810.04805",
    )

    store.create_candidate(db_path, run_id, candidate_1)
    store.create_candidate(db_path, run_id, candidate_2)

    # Get run detail through service
    service = ResearchPipelineService(db_path)
    detail = service.get_run_detail(run_id)

    # Verify candidates are present and correctly parsed
    assert len(detail.candidates) == 2

    c1 = detail.candidates[0]
    assert c1.paper_id == "paper_1"
    assert c1.source == "semantic_scholar"
    assert c1.title == "Attention Is All You Need"
    assert c1.authors == ["Vaswani", "Shazeer"]
    assert c1.year == 2017
    assert c1.semantic_scholar_id == "ss_1"
    assert c1.citation_count == 50000

    c2 = detail.candidates[1]
    assert c2.paper_id == "paper_2"
    assert c2.source == "arxiv"
    assert c2.title == "BERT: Pre-training of Deep Bidirectional Transformers"
    assert c2.authors == ["Devlin"]
    assert c2.year == 2018
    assert c2.arxiv_id == "1810.04805"


def test_service_get_run_detail_empty_candidates(tmp_path):
    """Service.get_run_detail should return empty list when no candidates."""
    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    # Create run without candidates
    run_id = store.create_run(
        db_path=db_path,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Get run detail through service
    service = ResearchPipelineService(db_path)
    detail = service.get_run_detail(run_id)

    # Verify candidates list is empty
    assert detail.candidates == []


def test_service_get_run_detail_preserves_candidate_metadata(tmp_path):
    """Service should preserve all candidate fields including metadata."""
    db_path = str(tmp_path / "test.db")
    store.init_db(db_path)

    run_id = store.create_run(
        db_path=db_path,
        question="Test question",
        source_mode="hybrid",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Create candidate with full metadata
    candidate = PaperCandidate(
        paper_id="paper_full",
        source="zotero",
        title="Full Metadata Paper",
        authors=["Author1", "Author2"],
        year=2020,
        venue="CVPR",
        abstract="This is the abstract",
        doi="10.1234/example",
        arxiv_id="2001.12345",
        semantic_scholar_id="ss_full",
        zotero_item_id="zot_123",
        url="https://example.com/paper",
        pdf_url="https://example.com/paper.pdf",
        local_pdf_path="/path/to/paper.pdf",
        citation_count=100,
        relevance_score=0.95,
        metadata={"source_collection": "ML Papers", "tags": ["transformers"]},
    )

    store.create_candidate(db_path, run_id, candidate)

    # Get run detail
    service = ResearchPipelineService(db_path)
    detail = service.get_run_detail(run_id)

    # Verify all fields preserved
    c = detail.candidates[0]
    assert c.paper_id == "paper_full"
    assert c.source == "zotero"
    assert c.title == "Full Metadata Paper"
    assert c.authors == ["Author1", "Author2"]
    assert c.year == 2020
    assert c.venue == "CVPR"
    assert c.abstract == "This is the abstract"
    assert c.doi == "10.1234/example"
    assert c.arxiv_id == "2001.12345"
    assert c.semantic_scholar_id == "ss_full"
    assert c.zotero_item_id == "zot_123"
    assert c.url == "https://example.com/paper"
    assert c.pdf_url == "https://example.com/paper.pdf"
    assert c.local_pdf_path == "/path/to/paper.pdf"
    assert c.citation_count == 100
    assert c.relevance_score == 0.95
    assert c.metadata == {"source_collection": "ML Papers", "tags": ["transformers"]}
