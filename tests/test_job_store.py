from app.schemas import JobStatusResponse
from app.services.job_store import FileJobStore, InMemoryJobStore


def _job(job_id: str, status: str = "queued") -> JobStatusResponse:
    kwargs = {
        "job_id": job_id,
        "job_type": "note_generation",
        "paper_id": "paper_001",
        "status": status,
        "progress": 0.0 if status == "queued" else 1.0,
        "created_at": "2026-05-21T00:00:00+00:00",
        "updated_at": "2026-05-21T00:00:00+00:00",
    }
    if status in {"completed", "cancelled"}:
        kwargs["started_at"] = "2026-05-21T00:00:01+00:00"
        kwargs["completed_at"] = "2026-05-21T00:00:02+00:00"
        kwargs["updated_at"] = "2026-05-21T00:00:02+00:00"
    if status == "running":
        kwargs["started_at"] = "2026-05-21T00:00:01+00:00"
        kwargs["progress"] = 0.5
    if status == "failed":
        kwargs["started_at"] = "2026-05-21T00:00:01+00:00"
        kwargs["progress"] = 0.5
        kwargs["error"] = "boom"
    return JobStatusResponse(**kwargs)


def test_in_memory_job_store_handles_generic_jobs():
    store = InMemoryJobStore()
    queued = _job("job_old")
    running = _job("job_new", "running")
    running.created_at = running.created_at.replace(minute=1)

    store.upsert(queued)
    store.upsert(running)

    assert store.get("job_new") == running
    assert [job.job_id for job in store.list()] == ["job_new", "job_old"]


def test_file_job_store_persists_generic_jobs(tmp_path):
    path = tmp_path / "jobs.json"
    store = FileJobStore(path)
    completed = _job("job_completed", "completed")
    completed.result = {"note_path": "notes/paper_001.md"}

    store.upsert(completed)
    reloaded = FileJobStore(path)

    job = reloaded.get("job_completed")
    assert job is not None
    assert job.job_type == "note_generation"
    assert job.status == "completed"
    assert job.result == {"note_path": "notes/paper_001.md"}


def test_job_status_lifecycle_accepts_cancelled_state():
    job = _job("job_cancelled", "cancelled")

    assert job.status == "cancelled"
    assert job.completed_at is not None
