"""
Test Research Pipeline Stub End-to-End

Validates complete workflow state machine with stub agents.
No LLM, API, or PDF dependencies.
"""

import tempfile
from pathlib import Path

import pytest

from app.research_pipeline.runner import PipelineRunner, StubAgent
from app.research_pipeline.store import create_run, get_run_detail, init_db


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_pipeline.sqlite3")
        init_db(db_path)
        yield db_path


def test_stub_pipeline_complete_lifecycle(temp_db):
    """
    Test complete run lifecycle with stub agents.

    Validates:
    - Run transitions: queued → running → completed
    - All 5 stages execute in order: planner, retriever, reader, synthesis, harness
    - Each stage transitions: queued → running → completed
    - Each stage writes at least one event
    - Final run status is completed
    """
    # Create run
    run_id = create_run(
        db_path=temp_db,
        question="What are the latest advances in LLMs?",
        source_mode="hybrid",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    # Verify initial state
    detail = get_run_detail(temp_db, run_id)
    assert detail["status"] == "queued"
    assert len(detail["stages"]) == 5
    assert all(stage["status"] == "queued" for stage in detail["stages"])
    assert len(detail["events"]) == 0

    # Execute pipeline
    runner = PipelineRunner(db_path=temp_db, agent_factory=StubAgent)
    runner.run(run_id)

    # Verify final state
    detail = get_run_detail(temp_db, run_id)

    # Verify run completed
    assert detail["status"] == "completed"
    assert detail["started_at"] is not None
    assert detail["completed_at"] is not None
    assert detail["error"] is None

    # Verify all stages completed
    stages = {stage["stage"]: stage for stage in detail["stages"]}
    assert len(stages) == 5

    expected_stages = ["planner", "retriever", "reader", "synthesis", "harness"]
    for stage_name in expected_stages:
        stage = stages[stage_name]
        assert stage["status"] == "completed", f"Stage {stage_name} not completed"
        assert stage["started_at"] is not None, f"Stage {stage_name} has no started_at"
        assert (
            stage["completed_at"] is not None
        ), f"Stage {stage_name} has no completed_at"
        assert stage["progress"] == 1.0, f"Stage {stage_name} progress not 1.0"
        assert stage["error"] is None, f"Stage {stage_name} has error"

    # Verify events were written
    events = detail["events"]
    assert len(events) > 0, "No events written"

    # Verify each stage has at least one event
    stage_events = {}
    for event in events:
        stage_name = event["stage"]
        if stage_name not in stage_events:
            stage_events[stage_name] = []
        stage_events[stage_name].append(event)

    for stage_name in expected_stages:
        assert stage_name in stage_events, f"No events for stage {stage_name}"
        assert (
            len(stage_events[stage_name]) >= 1
        ), f"Stage {stage_name} has no events"

    # Verify event structure
    for event in events:
        assert event["id"].startswith("event_")
        assert event["run_id"] == run_id
        assert event["stage"] in expected_stages or event["stage"] == "runner"
        assert event["level"] in ["debug", "info", "warning", "error"]
        assert isinstance(event["message"], str)
        assert isinstance(event["payload"], dict)
        assert event["created_at"] is not None


def test_stub_pipeline_failure_path(temp_db):
    """
    Test pipeline failure handling.

    Validates:
    - When a stage fails, run status becomes failed
    - Failed stage has error message
    - Run has error message
    - Subsequent stages do not execute
    """

    class FailingAgent:
        """Agent that always fails on reader stage."""

        def __init__(self, stage: str, db_path: str, run_id: str):
            self.stage = stage
            self.db_path = db_path
            self.run_id = run_id

        def execute(self):
            if self.stage == "reader":
                raise ValueError("Simulated reader failure")
            # Use stub agent for other stages
            stub = StubAgent(self.stage, self.db_path, self.run_id)
            return stub.execute()

    # Create run
    run_id = create_run(
        db_path=temp_db,
        question="Test failure handling",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=2,
    )

    # Execute pipeline with failing agent
    runner = PipelineRunner(db_path=temp_db, agent_factory=FailingAgent)

    with pytest.raises(ValueError, match="Simulated reader failure"):
        runner.run(run_id)

    # Verify failure state
    detail = get_run_detail(temp_db, run_id)

    # Run should be failed
    assert detail["status"] == "failed"
    assert detail["error"] is not None
    assert "ValueError" in detail["error"]
    assert "Simulated reader failure" in detail["error"]
    assert detail["failed_at"] is not None

    # Check stage statuses
    stages = {stage["stage"]: stage for stage in detail["stages"]}

    # Planner and retriever should have completed
    assert stages["planner"]["status"] == "completed"
    assert stages["retriever"]["status"] == "completed"

    # Reader should have failed
    assert stages["reader"]["status"] == "failed"
    assert stages["reader"]["error"] is not None
    assert "ValueError" in stages["reader"]["error"]

    # Synthesis and harness should still be queued (never started)
    assert stages["synthesis"]["status"] == "queued"
    assert stages["harness"]["status"] == "queued"

    # Verify error events were written
    events = detail["events"]
    error_events = [e for e in events if e["level"] == "error"]
    assert len(error_events) > 0, "No error events written"

    # At least one error event should mention the failure
    error_messages = [e["message"] for e in error_events]
    assert any("failed" in msg.lower() for msg in error_messages)


def test_stub_pipeline_stage_events(temp_db):
    """
    Test that each stage writes expected events.

    Validates event types and payloads for each stage.
    """
    # Create and run pipeline
    run_id = create_run(
        db_path=temp_db,
        question="Test stage events",
        source_mode="hybrid",
        max_reader_papers=3,
        reader_concurrency=1,
    )

    runner = PipelineRunner(db_path=temp_db, agent_factory=StubAgent)
    runner.run(run_id)

    # Get events
    detail = get_run_detail(temp_db, run_id)
    events = detail["events"]

    # Group events by stage
    stage_events = {}
    for event in events:
        stage_name = event["stage"]
        if stage_name not in stage_events:
            stage_events[stage_name] = []
        stage_events[stage_name].append(event)

    # Verify planner events
    planner_events = stage_events["planner"]
    assert len(planner_events) >= 3  # start + at least 1 progress + complete
    planner_messages = [e["message"] for e in planner_events]
    assert any("started" in msg for msg in planner_messages)
    assert any("completed" in msg for msg in planner_messages)

    # Verify retriever events
    retriever_events = stage_events["retriever"]
    assert len(retriever_events) >= 3
    retriever_messages = [e["message"] for e in retriever_events]
    assert any("started" in msg for msg in retriever_messages)
    assert any("completed" in msg for msg in retriever_messages)

    # Verify reader events (should have multiple progress events)
    reader_events = stage_events["reader"]
    assert len(reader_events) >= 4  # start + 3 papers + complete
    reader_messages = [e["message"] for e in reader_events]
    assert any("started" in msg for msg in reader_messages)
    assert any("completed" in msg for msg in reader_messages)

    # Verify synthesis events
    synthesis_events = stage_events["synthesis"]
    assert len(synthesis_events) >= 3
    synthesis_messages = [e["message"] for e in synthesis_events]
    assert any("started" in msg for msg in synthesis_messages)
    assert any("completed" in msg for msg in synthesis_messages)

    # Verify harness events
    harness_events = stage_events["harness"]
    assert len(harness_events) >= 3
    harness_messages = [e["message"] for e in harness_events]
    assert any("started" in msg for msg in harness_messages)
    assert any("completed" in msg for msg in harness_messages)


def test_stub_pipeline_timestamps(temp_db):
    """
    Test that timestamps are set correctly throughout lifecycle.

    Validates:
    - Run timestamps: created_at, started_at, completed_at
    - Stage timestamps: started_at, completed_at
    - Timestamps are in chronological order
    """
    # Create and run pipeline
    run_id = create_run(
        db_path=temp_db,
        question="Test timestamps",
        source_mode="web_search",
        max_reader_papers=5,
        reader_concurrency=2,
    )

    runner = PipelineRunner(db_path=temp_db, agent_factory=StubAgent)
    runner.run(run_id)

    # Get detail
    detail = get_run_detail(temp_db, run_id)

    # Verify run timestamps
    assert detail["created_at"] is not None
    assert detail["started_at"] is not None
    assert detail["completed_at"] is not None
    assert detail["created_at"] <= detail["started_at"]
    assert detail["started_at"] <= detail["completed_at"]

    # Verify stage timestamps
    for stage in detail["stages"]:
        assert stage["started_at"] is not None, f"Stage {stage['stage']} has no started_at"
        assert (
            stage["completed_at"] is not None
        ), f"Stage {stage['stage']} has no completed_at"
        assert (
            stage["started_at"] <= stage["completed_at"]
        ), f"Stage {stage['stage']} timestamps out of order"


def test_stub_pipeline_progress_tracking(temp_db):
    """
    Test that progress is tracked correctly.

    Validates:
    - Stage progress starts at 0.0
    - Stage progress ends at 1.0 when completed
    """
    # Create and run pipeline
    run_id = create_run(
        db_path=temp_db,
        question="Test progress",
        source_mode="hybrid",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    runner = PipelineRunner(db_path=temp_db, agent_factory=StubAgent)
    runner.run(run_id)

    # Get detail
    detail = get_run_detail(temp_db, run_id)

    # Verify all stages have progress = 1.0
    for stage in detail["stages"]:
        assert (
            stage["progress"] == 1.0
        ), f"Stage {stage['stage']} progress is {stage['progress']}, expected 1.0"
        assert (
            stage["status"] == "completed"
        ), f"Stage {stage['stage']} status is {stage['status']}"
