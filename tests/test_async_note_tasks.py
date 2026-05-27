from fastapi.testclient import TestClient

from app.main import app


def _reset_job_store():
    from app.main import _get_job_store

    _get_job_store().clear()


def test_submit_note_task_runs_in_background_and_stores_result(monkeypatch, tmp_path):
    _reset_job_store()
    client = TestClient(app)

    monkeypatch.setattr("app.main._resolve_note_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        "app.main.generate_note", lambda paper_id: f"# Note for {paper_id}"
    )

    response = client.post("/tasks/note/paper_NOTE")

    assert response.status_code == 202
    body = response.json()
    assert body["job_type"] == "note_generation"
    assert body["paper_id"] == "paper_NOTE"

    detail = client.get(f"/tasks/{body['job_id']}").json()
    assert detail["status"] == "completed"
    assert detail["progress"] == 1.0
    assert detail["result"]["paper_id"] == "paper_NOTE"
    assert detail["result"]["note_path"].endswith("paper_NOTE_note.md")

    result = client.get(f"/tasks/{body['job_id']}/result")
    assert result.status_code == 200
    assert result.json()["content_preview"] == "# Note for paper_NOTE"


def test_submit_note_task_records_failure(monkeypatch):
    _reset_job_store()
    client = TestClient(app)

    def fail(_paper_id):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("app.main.generate_note", fail)

    response = client.post("/tasks/note/paper_FAIL")

    assert response.status_code == 202
    detail = client.get(f"/tasks/{response.json()['job_id']}").json()
    assert detail["status"] == "failed"
    assert detail["error"] == "LLM unavailable"


def test_task_result_returns_conflict_until_completed():
    _reset_job_store()
    client = TestClient(app)
    from app.main import _get_job_store
    from app.services.paper_status import build_job_status

    job = build_job_status(
        job_id="job_note_queued",
        job_type="note_generation",
        paper_id="paper_queued",
        status="queued",
        created_at="2026-05-21T00:00:00+00:00",
        updated_at="2026-05-21T00:00:00+00:00",
    )
    _get_job_store().upsert(job)

    response = client.get("/tasks/job_note_queued/result")

    assert response.status_code == 409
