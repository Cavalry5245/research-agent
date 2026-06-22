"""
Test Research Pipeline Service Layer

Service sits between FastAPI routes and store, handling business logic,
validation, and response assembly.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

import pytest
from pydantic import ValidationError

from app.research_pipeline import store
from app.research_pipeline.schemas import ResearchRunCreateRequest
from app.research_pipeline.service import ResearchPipelineService
from app.research_pipeline.store import get_run_detail, init_db, update_run_status


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_pipeline.sqlite3")
        init_db(db_path)
        yield db_path


@pytest.fixture
def service(temp_db):
    """Create a service instance."""
    return ResearchPipelineService(db_path=temp_db)


# ==================== create_run Tests ====================


def test_create_run_success(service):
    """Test create_run validates and creates a queued run."""
    request = ResearchRunCreateRequest(
        question="What are the latest advances in LLMs?",
        source_mode="hybrid",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    # Mock runner scheduler (don't actually start background task)
    scheduled_runs = []

    def mock_scheduler(run_id: str):
        scheduled_runs.append(run_id)

    response = service.create_run(request, runner_scheduler=mock_scheduler)

    assert response.run_id.startswith("run_")
    assert response.status == "queued"
    assert isinstance(response.created_at, datetime)

    # Verify runner was scheduled
    assert len(scheduled_runs) == 1
    assert scheduled_runs[0] == response.run_id


def test_create_run_validates_max_reader_papers_min(service):
    """Test create_run validates max_reader_papers >= 3."""
    with pytest.raises(ValidationError, match="greater than or equal to 3"):
        request = ResearchRunCreateRequest(
            question="Test question",
            source_mode="web_search",
            max_reader_papers=2,  # Too low
            reader_concurrency=3,
        )
        service.create_run(request)


def test_create_run_validates_max_reader_papers_max(service):
    """Test create_run validates max_reader_papers <= 15."""
    with pytest.raises(ValidationError, match="less than or equal to 15"):
        request = ResearchRunCreateRequest(
            question="Test question",
            source_mode="web_search",
            max_reader_papers=20,  # Too high
            reader_concurrency=3,
        )
        service.create_run(request)


def test_create_run_validates_reader_concurrency(service):
    """Test create_run validates reader_concurrency >= 1."""
    with pytest.raises(ValueError, match="reader_concurrency must be >= 1"):
        request = ResearchRunCreateRequest(
            question="Test question",
            source_mode="web_search",
            max_reader_papers=8,
            reader_concurrency=0,  # Invalid
        )
        service.create_run(request)


def test_create_run_validates_empty_question(service):
    """Test create_run validates question is not empty."""
    with pytest.raises(ValueError, match="question cannot be empty"):
        request = ResearchRunCreateRequest(
            question="   ",  # Empty after strip
            source_mode="web_search",
            max_reader_papers=8,
            reader_concurrency=3,
        )
        service.create_run(request)


def test_create_run_validates_zotero_key_when_zotero_only(service):
    """Test create_run validates zotero_collection_key when source_mode is zotero_only."""
    with pytest.raises(
        ValueError, match="zotero_collection_key required when source_mode is zotero_only"
    ):
        request = ResearchRunCreateRequest(
            question="Test question",
            source_mode="zotero_only",
            zotero_collection_key=None,  # Missing
            max_reader_papers=8,
            reader_concurrency=3,
        )
        service.create_run(request)


def test_create_run_accepts_zotero_key_when_zotero_only(service):
    """Test create_run succeeds when zotero_only with key provided."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="zotero_only",
        zotero_collection_key="ABC123",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    response = service.create_run(request)
    assert response.run_id.startswith("run_")
    assert response.status == "queued"


def test_create_run_with_optional_filters(service):
    """Test create_run with year and venue filters."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=10,
        reader_concurrency=5,
        year_start=2020,
        year_end=2024,
        venue_filter=["NeurIPS", "ICML"],
        keywords=["attention", "transformers"],
    )

    response = service.create_run(request)
    assert response.run_id.startswith("run_")

    # Verify stored data
    detail = get_run_detail(service.db_path, response.run_id)
    assert detail["year_start"] == 2020
    assert detail["year_end"] == 2024
    assert detail["venue_filter"] == ["NeurIPS", "ICML"]
    assert detail["keywords"] == ["attention", "transformers"]


def test_create_run_uses_default_scheduler_if_none_provided(service):
    """Test create_run uses default runner scheduler when none provided."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    # Should not raise; uses default no-op scheduler
    response = service.create_run(request)
    assert response.run_id.startswith("run_")


# ==================== list_runs Tests ====================


def test_list_runs_returns_empty_list_when_no_runs(service):
    """Test list_runs returns empty list when no runs exist."""
    response = service.list_runs()

    assert response.count == 0
    assert response.runs == []


def test_list_runs_returns_runs_in_reverse_chronological_order(service):
    """Test list_runs returns runs newest first."""
    # Create 3 runs
    req1 = ResearchRunCreateRequest(
        question="First question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    resp1 = service.create_run(req1)

    req2 = ResearchRunCreateRequest(
        question="Second question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    resp2 = service.create_run(req2)

    req3 = ResearchRunCreateRequest(
        question="Third question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    resp3 = service.create_run(req3)

    response = service.list_runs()

    assert response.count == 3
    # Newest first
    assert response.runs[0].run_id == resp3.run_id
    assert response.runs[1].run_id == resp2.run_id
    assert response.runs[2].run_id == resp1.run_id


def test_list_runs_respects_limit(service):
    """Test list_runs respects the limit parameter."""
    # Create 5 runs
    for i in range(5):
        req = ResearchRunCreateRequest(
            question=f"Question {i}",
            source_mode="web_search",
            max_reader_papers=8,
            reader_concurrency=3,
        )
        service.create_run(req)

    response = service.list_runs(limit=3)

    assert response.count == 3
    assert len(response.runs) == 3


# ==================== get_run_detail Tests ====================


def test_get_run_detail_returns_full_response_structure(service):
    """Test get_run_detail returns frontend-ready response with all fields."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    detail = service.get_run_detail(create_resp.run_id)

    assert detail is not None
    assert detail.run_id == create_resp.run_id
    assert detail.question == "Test question"
    assert detail.status == "queued"
    assert detail.source_mode == "web_search"
    assert detail.max_reader_papers == 8
    assert detail.reader_concurrency == 3

    # Verify empty arrays are initialized
    assert len(detail.stages) == 5  # 5 stages initialized
    assert detail.events == []  # No events yet
    assert detail.candidates == []  # Empty for now
    assert detail.cards == []  # Empty for now
    assert detail.plan is None  # No plan yet
    assert detail.report is None  # No report yet


def test_get_run_detail_includes_latest_plan_and_report(service):
    """Test get_run_detail returns persisted plan and report for frontend preview."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    store.create_plan(
        service.db_path,
        create_resp.run_id,
        phase="initial",
        plan_data={"normalized_question": "Test question", "queries": ["Test question"]},
    )
    store.save_report(
        service.db_path,
        create_resp.run_id,
        markdown="# Test Report",
        template_version="research_pipeline_v1",
    )

    detail = service.get_run_detail(create_resp.run_id)

    assert detail.plan is not None
    assert detail.plan.phase == "initial"
    assert detail.report is not None
    assert detail.report.markdown == "# Test Report"


def test_get_run_detail_nonexistent_run_raises_404(service):
    """Test get_run_detail raises ValueError for non-existent run."""
    with pytest.raises(ValueError, match="Run run_nonexistent not found"):
        service.get_run_detail("run_nonexistent")


def test_get_run_detail_includes_stages(service):
    """Test get_run_detail includes stage data."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    detail = service.get_run_detail(create_resp.run_id)

    assert len(detail.stages) == 5
    stage_names = [s.stage for s in detail.stages]
    assert set(stage_names) == {"planner", "retriever", "reader", "synthesis", "harness"}

    # All stages should be queued initially
    for stage in detail.stages:
        assert stage.status == "queued"
        assert stage.progress == 0.0


# ==================== cancel_run Tests ====================


def test_cancel_run_succeeds_for_queued_run(service):
    """Test cancel_run succeeds for a queued run."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    # Cancel the queued run
    service.cancel_run(create_resp.run_id)

    # Verify status changed to cancelled
    detail = service.get_run_detail(create_resp.run_id)
    assert detail.status == "cancelled"
    assert detail.cancelled_at is not None


def test_cancel_run_succeeds_for_running_run(service):
    """Test cancel_run succeeds for a running run."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    # Update to running
    update_run_status(service.db_path, create_resp.run_id, "running")

    # Cancel the running run
    service.cancel_run(create_resp.run_id)

    # Verify status changed to cancelled
    detail = service.get_run_detail(create_resp.run_id)
    assert detail.status == "cancelled"


def test_cancel_run_succeeds_for_degraded_run(service):
    """Test cancel_run succeeds for a degraded run."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    # Update to degraded
    update_run_status(service.db_path, create_resp.run_id, "degraded")

    # Cancel the degraded run
    service.cancel_run(create_resp.run_id)

    # Verify status changed to cancelled
    detail = service.get_run_detail(create_resp.run_id)
    assert detail.status == "cancelled"


def test_cancel_run_fails_for_completed_run(service):
    """Test cancel_run returns conflict error for completed run."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    # Update to completed
    update_run_status(service.db_path, create_resp.run_id, "completed")

    # Attempt to cancel should raise conflict
    with pytest.raises(
        ValueError, match="Cannot cancel run with status completed. Only queued, running, or degraded runs can be cancelled."
    ):
        service.cancel_run(create_resp.run_id)


def test_cancel_run_fails_for_failed_run(service):
    """Test cancel_run returns conflict error for failed run."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    # Update to failed
    update_run_status(service.db_path, create_resp.run_id, "failed", error="Test error")

    # Attempt to cancel should raise conflict
    with pytest.raises(
        ValueError, match="Cannot cancel run with status failed. Only queued, running, or degraded runs can be cancelled."
    ):
        service.cancel_run(create_resp.run_id)


def test_cancel_run_fails_for_already_cancelled_run(service):
    """Test cancel_run returns conflict error for already cancelled run."""
    request = ResearchRunCreateRequest(
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    # Cancel once
    service.cancel_run(create_resp.run_id)

    # Attempt to cancel again should raise conflict
    with pytest.raises(
        ValueError, match="Cannot cancel run with status cancelled. Only queued, running, or degraded runs can be cancelled."
    ):
        service.cancel_run(create_resp.run_id)


def test_cancel_run_nonexistent_run_raises_404(service):
    """Test cancel_run raises ValueError for non-existent run."""
    with pytest.raises(ValueError, match="Run run_nonexistent not found"):
        service.cancel_run("run_nonexistent")


def test_delete_run_removes_existing_run(service):
    """Test delete_run removes a run from the service store."""
    request = ResearchRunCreateRequest(
        question="Delete this run",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    create_resp = service.create_run(request)

    service.delete_run(create_resp.run_id)

    with pytest.raises(ValueError, match=f"Run {create_resp.run_id} not found"):
        service.get_run_detail(create_resp.run_id)


def test_delete_run_nonexistent_run_raises_404(service):
    """Test delete_run raises ValueError for non-existent run."""
    with pytest.raises(ValueError, match="Run run_nonexistent not found"):
        service.delete_run("run_nonexistent")
