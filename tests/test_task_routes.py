from fastapi.testclient import TestClient

from app.main import app
from app.services.paper_status import build_job_status


def _reset_job_store():
    from app.main import _get_job_store

    _get_job_store().clear()


def _store(job):
    from app.main import _get_job_store

    _get_job_store().upsert(job)


def test_task_list_and_status_routes_return_generic_jobs():
    _reset_job_store()
    client = TestClient(app)
    job = build_job_status(
        job_id="job_note_list",
        job_type="note_generation",
        paper_id="paper_001",
        status="queued",
        created_at="2026-05-21T00:00:00+00:00",
        updated_at="2026-05-21T00:00:00+00:00",
    )
    _store(job)

    list_response = client.get("/tasks")
    detail_response = client.get("/tasks/job_note_list")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["job_type"] == "note_generation"


def test_cancel_queued_task():
    _reset_job_store()
    client = TestClient(app)
    job = build_job_status(
        job_id="job_note_cancel",
        job_type="note_generation",
        paper_id="paper_001",
        status="queued",
        created_at="2026-05-21T00:00:00+00:00",
        updated_at="2026-05-21T00:00:00+00:00",
    )
    _store(job)

    response = client.delete("/tasks/job_note_cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["error"] == "任务已取消"


def test_cancel_completed_task_returns_conflict():
    _reset_job_store()
    client = TestClient(app)
    job = build_job_status(
        job_id="job_note_done",
        job_type="note_generation",
        paper_id="paper_001",
        status="completed",
        created_at="2026-05-21T00:00:00+00:00",
        started_at="2026-05-21T00:00:01+00:00",
        completed_at="2026-05-21T00:00:02+00:00",
        updated_at="2026-05-21T00:00:02+00:00",
        progress=1.0,
    )
    _store(job)

    response = client.delete("/tasks/job_note_done")

    assert response.status_code == 409


def test_retry_failed_note_task(monkeypatch):
    _reset_job_store()
    client = TestClient(app)
    job = build_job_status(
        job_id="job_note_failed",
        job_type="note_generation",
        paper_id="paper_001",
        status="failed",
        created_at="2026-05-21T00:00:00+00:00",
        started_at="2026-05-21T00:00:01+00:00",
        updated_at="2026-05-21T00:00:02+00:00",
        progress=0.2,
        error="failed",
    )
    _store(job)
    monkeypatch.setattr("app.main.generate_note", lambda paper_id: "# retry ok")

    response = client.post("/tasks/job_note_failed/retry")

    assert response.status_code == 202
    body = response.json()
    assert body["original_job_id"] == "job_note_failed"
    assert body["retry_job"]["retry_of"] == "job_note_failed"
    retry_detail = client.get(f"/tasks/{body['retry_job']['job_id']}").json()
    assert retry_detail["status"] == "completed"


def test_retry_non_failed_task_returns_conflict():
    _reset_job_store()
    client = TestClient(app)
    job = build_job_status(
        job_id="job_note_running",
        job_type="note_generation",
        paper_id="paper_001",
        status="queued",
        created_at="2026-05-21T00:00:00+00:00",
        updated_at="2026-05-21T00:00:00+00:00",
    )
    _store(job)

    response = client.post("/tasks/job_note_running/retry")

    assert response.status_code == 409
