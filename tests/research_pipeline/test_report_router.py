"""
Tests for Report API endpoints.

Tests GET /research-pipeline/runs/{run_id}/report (JSON)
and GET /research-pipeline/runs/{run_id}/report.md (markdown file).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.research_pipeline import store
from app.research_pipeline import router
from app.research_pipeline.service import ResearchPipelineService


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db_file = tmp_path / "test_report_router.db"
    store.init_db(str(db_file))
    return str(db_file)


@pytest.fixture
def client_with_db(db_path):
    """Create test client with dependency override for database."""
    def get_test_service():
        return ResearchPipelineService(db_path=db_path)

    app.dependency_overrides[router.get_service] = get_test_service
    client = TestClient(app)
    yield client, db_path
    app.dependency_overrides.clear()


@pytest.fixture
def run_with_report(db_path):
    """Create a test run with a report and claims."""
    # Ensure all tables exist (including research_reports and report_claims)
    store.init_db(db_path)

    # Create run
    run_id = store.create_run(
        db_path=db_path,
        question="Test question?",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    # Save report
    report_markdown = """# Research Report

## Summary
This is a test report.

## Key Findings
- Finding 1
- Finding 2
"""
    report_id = store.save_report(
        db_path=db_path,
        run_id=run_id,
        markdown=report_markdown,
        template_version="v1.0",
    )

    # Save claims with different verification statuses
    claims = [
        {
            "claim_text": "Model achieves 95% accuracy",
            "claim_type": "result",
            "citation_ids": ["paper1"],
            "evidence_ids": ["ev1"],
            "verification_status": "supported",
            "verification_reason": "Cited in paper1",
        },
        {
            "claim_text": "Dataset contains 1M samples",
            "claim_type": "dataset",
            "citation_ids": ["paper2"],
            "evidence_ids": [],
            "verification_status": "weak",
            "verification_reason": "Partial evidence",
        },
        {
            "claim_text": "Method is novel",
            "claim_type": "method",
            "citation_ids": [],
            "evidence_ids": [],
            "verification_status": "unverified",
            "verification_reason": "No evidence found",
        },
    ]

    store.save_claims(
        db_path=db_path,
        run_id=run_id,
        report_id=report_id,
        claims=claims,
    )

    return {
        "run_id": run_id,
        "report_id": report_id,
        "markdown": report_markdown,
        "db_path": db_path,
    }


def test_get_report_json_returns_complete_structure(run_with_report, client_with_db):
    """
    RED: Test that GET /research-pipeline/runs/{run_id}/report returns
    JSON with markdown, claims, and summary.
    """
    client, _ = client_with_db

    # Make request
    response = client.get(
        f"/research-pipeline/runs/{run_with_report['run_id']}/report"
    )

    # Should return 200
    assert response.status_code == 200

    # Should have JSON structure
    data = response.json()
    assert "markdown" in data
    assert "claims" in data
    assert "summary" in data

    # Markdown should match
    assert data["markdown"] == run_with_report["markdown"]

    # Claims should be present
    assert len(data["claims"]) == 3
    claim_texts = [c["claim_text"] for c in data["claims"]]
    assert "Model achieves 95% accuracy" in claim_texts

    # Summary should have counts
    summary = data["summary"]
    assert summary["supported"] == 1
    assert summary["weak"] == 1
    assert summary["unverified"] == 1
    assert summary["numeric_trace_missing"] == 0
    assert summary["conflict_detected"] == 0
    assert summary["total"] == 3


def test_get_report_markdown_file_returns_text_markdown(run_with_report, client_with_db):
    """
    RED: Test that GET /research-pipeline/runs/{run_id}/report.md returns
    text/markdown with correct content-disposition header.
    """
    client, _ = client_with_db

    # Make request
    response = client.get(
        f"/research-pipeline/runs/{run_with_report['run_id']}/report.md"
    )

    # Should return 200
    assert response.status_code == 200

    # Should have markdown content type
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"

    # Should have content-disposition for download
    assert "content-disposition" in response.headers
    assert "attachment" in response.headers["content-disposition"]
    assert "report.md" in response.headers["content-disposition"]

    # Content should match markdown
    assert response.text == run_with_report["markdown"]


def test_get_report_json_returns_404_when_not_found(client_with_db):
    """
    RED: Test that GET /research-pipeline/runs/{run_id}/report returns 404
    when report does not exist.
    """
    client, _ = client_with_db

    # Request report for non-existent run
    response = client.get("/research-pipeline/runs/nonexistent/report")

    # Should return 404
    assert response.status_code == 404
    data = response.json()
    assert "message" in data
    assert "not found" in data["message"].lower()


def test_get_report_markdown_returns_404_when_not_found(client_with_db):
    """
    RED: Test that GET /research-pipeline/runs/{run_id}/report.md returns 404
    when report does not exist.
    """
    client, _ = client_with_db

    # Request markdown for non-existent run
    response = client.get("/research-pipeline/runs/nonexistent/report.md")

    # Should return 404
    assert response.status_code == 404
    data = response.json()
    assert "message" in data
    assert "not found" in data["message"].lower()


def test_get_report_json_returns_empty_claims_when_no_claims(client_with_db):
    """
    RED: Test that report endpoint handles runs with report but no claims.
    """
    client, db_path = client_with_db

    # Create run with report but no claims
    run_id = store.create_run(
        db_path=db_path,
        question="Test question?",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=3,
    )

    markdown = "# Report with no claims"
    store.save_report(
        db_path=db_path,
        run_id=run_id,
        markdown=markdown,
        template_version="v1.0",
    )

    # Make request
    response = client.get(f"/research-pipeline/runs/{run_id}/report")

    # Should return 200
    assert response.status_code == 200

    data = response.json()
    assert data["markdown"] == markdown
    assert data["claims"] == []
    assert data["summary"]["total"] == 0
    assert data["summary"]["supported"] == 0
