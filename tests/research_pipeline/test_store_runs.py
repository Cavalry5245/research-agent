"""
Test CRUD operations for research runs, stages, and events.
"""

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.research_pipeline.store import (
    append_event,
    create_candidate,
    create_run,
    delete_run,
    get_run_detail,
    init_db,
    list_runs,
    save_claims,
    save_report,
    update_run_status,
    update_stage,
)
from app.research_pipeline.schemas import PaperCandidate


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_pipeline.sqlite3")
        init_db(db_path)
        yield db_path


def test_create_run_initializes_five_stages(temp_db):
    """Test that create_run writes run and initializes 5 stages."""
    run_id = create_run(
        db_path=temp_db,
        question="What are the latest advances in transformer models?",
        source_mode="hybrid",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    assert run_id.startswith("run_")

    # Verify run was created
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,))
    run_row = cursor.fetchone()
    assert run_row is not None
    assert run_row["question"] == "What are the latest advances in transformer models?"
    assert run_row["source_mode"] == "hybrid"
    assert run_row["status"] == "queued"
    assert run_row["max_reader_papers"] == 8
    assert run_row["reader_concurrency"] == 3

    # Verify 5 stages were initialized
    cursor.execute(
        "SELECT stage FROM research_run_stages WHERE run_id = ? ORDER BY stage",
        (run_id,),
    )
    stages = [row["stage"] for row in cursor.fetchall()]
    assert stages == ["harness", "planner", "reader", "retriever", "synthesis"]

    # Verify all stages have queued status
    cursor.execute(
        "SELECT status FROM research_run_stages WHERE run_id = ?",
        (run_id,),
    )
    statuses = [row["status"] for row in cursor.fetchall()]
    assert all(status == "queued" for status in statuses)

    conn.close()


def test_create_run_with_optional_fields(temp_db):
    """Test create_run with optional fields."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="zotero_only",
        zotero_collection_key="ABC123",
        max_reader_papers=10,
        reader_concurrency=5,
        year_start=2020,
        year_end=2024,
        venue_filter=["NeurIPS", "ICML"],
        keywords=["attention", "transformers"],
    )

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,))
    run_row = cursor.fetchone()

    assert run_row["zotero_collection_key"] == "ABC123"
    assert run_row["year_start"] == 2020
    assert run_row["year_end"] == 2024
    assert json.loads(run_row["venue_filter_json"]) == ["NeurIPS", "ICML"]
    assert json.loads(run_row["keywords_json"]) == ["attention", "transformers"]

    conn.close()


def test_get_run_detail_returns_combined_data(temp_db):
    """Test get_run_detail returns run + stages + events."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    # Add an event
    append_event(
        db_path=temp_db,
        run_id=run_id,
        stage="planner",
        level="info",
        message="Planner started",
        payload={"key": "value"},
    )

    detail = get_run_detail(db_path=temp_db, run_id=run_id)

    assert detail is not None
    assert detail["run_id"] == run_id
    assert detail["question"] == "Test question"
    assert detail["status"] == "queued"
    assert len(detail["stages"]) == 5
    assert len(detail["events"]) == 1
    assert detail["events"][0]["message"] == "Planner started"
    assert detail["events"][0]["payload"] == {"key": "value"}


def test_get_run_detail_nonexistent_run(temp_db):
    """Test get_run_detail returns None for non-existent run."""
    detail = get_run_detail(db_path=temp_db, run_id="run_nonexistent")
    assert detail is None


def test_list_runs_reverse_chronological(temp_db):
    """Test list_runs returns runs in reverse chronological order."""
    # Create 3 runs with slight delays to ensure different timestamps
    run_id_1 = create_run(
        db_path=temp_db,
        question="First question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    run_id_2 = create_run(
        db_path=temp_db,
        question="Second question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    run_id_3 = create_run(
        db_path=temp_db,
        question="Third question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    runs = list_runs(db_path=temp_db, limit=10)

    assert len(runs) == 3
    # Most recent first
    assert runs[0]["run_id"] == run_id_3
    assert runs[1]["run_id"] == run_id_2
    assert runs[2]["run_id"] == run_id_1


def test_list_runs_respects_limit(temp_db):
    """Test list_runs respects the limit parameter."""
    for i in range(5):
        create_run(
            db_path=temp_db,
            question=f"Question {i}",
            source_mode="web_search",
            max_reader_papers=8,
            reader_concurrency=3,
        )

    runs = list_runs(db_path=temp_db, limit=3)
    assert len(runs) == 3


def test_delete_run_removes_run_and_owned_records(temp_db):
    """Delete should remove the run and all child records owned by it."""
    run_id = create_run(
        db_path=temp_db,
        question="Delete me",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    append_event(temp_db, run_id, "planner", "info", "Planning")
    create_candidate(
        temp_db,
        run_id,
        PaperCandidate(
            paper_id="paper_1",
            source="arxiv",
            title="Paper 1",
        ),
    )
    report_id = save_report(
        temp_db,
        run_id,
        markdown="# Report",
        template_version="research_pipeline_v1",
    )
    save_claims(
        temp_db,
        run_id,
        report_id,
        [
            {
                "claim_text": "Claim",
                "claim_type": "method",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "unverified",
                "verification_reason": "Test",
            }
        ],
    )

    assert delete_run(temp_db, run_id) is True
    assert get_run_detail(temp_db, run_id) is None

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    try:
        for table in [
            "research_run_stages",
            "research_run_events",
            "research_plans",
            "paper_candidates",
            "research_reports",
            "report_claims",
        ]:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id = ?", (run_id,))
            assert cursor.fetchone()[0] == 0
    finally:
        conn.close()


def test_delete_run_returns_false_for_missing_run(temp_db):
    """Delete should report false when the run does not exist."""
    assert delete_run(temp_db, "run_missing") is False


def test_update_run_status(temp_db):
    """Test update_run_status updates run status correctly."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    # Update to running
    success = update_run_status(
        db_path=temp_db,
        run_id=run_id,
        status="running",
    )
    assert success is True

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    assert detail["status"] == "running"
    assert detail["started_at"] is not None

    # Update to completed
    success = update_run_status(
        db_path=temp_db,
        run_id=run_id,
        status="completed",
    )
    assert success is True

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    assert detail["status"] == "completed"
    assert detail["completed_at"] is not None


def test_update_run_status_with_error(temp_db):
    """Test update_run_status with error message."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    success = update_run_status(
        db_path=temp_db,
        run_id=run_id,
        status="failed",
        error="Something went wrong",
    )
    assert success is True

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    assert detail["status"] == "failed"
    assert detail["error"] == "Something went wrong"
    assert detail["failed_at"] is not None


def test_update_run_status_nonexistent_run(temp_db):
    """Test update_run_status returns False for non-existent run."""
    success = update_run_status(
        db_path=temp_db,
        run_id="run_nonexistent",
        status="running",
    )
    assert success is False


def test_update_stage(temp_db):
    """Test update_stage updates stage correctly."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    # Update planner stage to running
    success = update_stage(
        db_path=temp_db,
        run_id=run_id,
        stage="planner",
        status="running",
        progress=0.5,
        message="Processing query",
    )
    assert success is True

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    planner_stage = next(s for s in detail["stages"] if s["stage"] == "planner")
    assert planner_stage["status"] == "running"
    assert planner_stage["progress"] == 0.5
    assert planner_stage["message"] == "Processing query"
    assert planner_stage["started_at"] is not None


def test_update_stage_completion(temp_db):
    """Test update_stage sets completed_at when status is completed."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    success = update_stage(
        db_path=temp_db,
        run_id=run_id,
        stage="planner",
        status="completed",
        progress=1.0,
        message="Planning complete",
    )
    assert success is True

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    planner_stage = next(s for s in detail["stages"] if s["stage"] == "planner")
    assert planner_stage["status"] == "completed"
    assert planner_stage["completed_at"] is not None


def test_update_stage_with_error(temp_db):
    """Test update_stage with error message."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    success = update_stage(
        db_path=temp_db,
        run_id=run_id,
        stage="retriever",
        status="failed",
        progress=0.3,
        message="Failed to fetch papers",
        error="Network timeout",
    )
    assert success is True

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    retriever_stage = next(s for s in detail["stages"] if s["stage"] == "retriever")
    assert retriever_stage["status"] == "failed"
    assert retriever_stage["error"] == "Network timeout"


def test_update_stage_nonexistent_run(temp_db):
    """Test update_stage returns False for non-existent run."""
    success = update_stage(
        db_path=temp_db,
        run_id="run_nonexistent",
        stage="planner",
        status="running",
    )
    assert success is False


def test_append_event(temp_db):
    """Test append_event saves event correctly."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    event_id = append_event(
        db_path=temp_db,
        run_id=run_id,
        stage="planner",
        level="info",
        message="Test event",
        payload={"data": "test"},
    )

    assert event_id.startswith("event_")

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    assert len(detail["events"]) == 1
    event = detail["events"][0]
    assert event["stage"] == "planner"
    assert event["level"] == "info"
    assert event["message"] == "Test event"
    assert event["payload"] == {"data": "test"}


def test_append_event_multiple_events(temp_db):
    """Test appending multiple events preserves order."""
    run_id = create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    append_event(
        db_path=temp_db,
        run_id=run_id,
        stage="planner",
        level="info",
        message="Event 1",
    )

    append_event(
        db_path=temp_db,
        run_id=run_id,
        stage="retriever",
        level="debug",
        message="Event 2",
    )

    append_event(
        db_path=temp_db,
        run_id=run_id,
        stage="planner",
        level="warning",
        message="Event 3",
    )

    detail = get_run_detail(db_path=temp_db, run_id=run_id)
    assert len(detail["events"]) == 3
    assert detail["events"][0]["message"] == "Event 1"
    assert detail["events"][1]["message"] == "Event 2"
    assert detail["events"][2]["message"] == "Event 3"


def test_foreign_key_constraints_enabled(temp_db):
    """Test that foreign key constraints are properly enabled."""
    # Try to create an event for a non-existent run
    conn = sqlite3.connect(temp_db)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO research_run_events
            (id, run_id, stage, level, message, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event_test",
                "run_nonexistent",
                "planner",
                "info",
                "test",
                "{}",
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()

    conn.close()
