from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.schemas import IndexJobStatusResponse, JobStatusResponse


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobStatusResponse] = {}
        self._lock = Lock()

    def upsert(self, job: JobStatusResponse) -> JobStatusResponse:
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobStatusResponse | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[JobStatusResponse]:
        with self._lock:
            return sorted(
                self._jobs.values(), key=lambda job: job.created_at, reverse=True
            )

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()


class FileJobStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, job: JobStatusResponse) -> JobStatusResponse:
        with self._lock:
            jobs = self._load_jobs_unlocked()
            jobs[job.job_id] = job
            self._save_jobs_unlocked(jobs)
        return job

    def get(self, job_id: str) -> JobStatusResponse | None:
        with self._lock:
            return self._load_jobs_unlocked().get(job_id)

    def list(self) -> list[JobStatusResponse]:
        with self._lock:
            jobs = self._load_jobs_unlocked()
            return sorted(jobs.values(), key=lambda job: job.created_at, reverse=True)

    def clear(self) -> None:
        with self._lock:
            self._save_jobs_unlocked({})

    def _load_jobs_unlocked(self) -> dict[str, JobStatusResponse]:
        if not self._path.exists():
            return {}

        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}

        payload = json.loads(raw)
        jobs: dict[str, JobStatusResponse] = {}
        for item in payload.get("jobs", []):
            model = (
                IndexJobStatusResponse
                if item.get("job_type") == "paper_index"
                else JobStatusResponse
            )
            job = model.model_validate(item)
            jobs[job.job_id] = job
        return jobs

    def _save_jobs_unlocked(self, jobs: dict[str, JobStatusResponse]) -> None:
        payload = {
            "jobs": [job.model_dump(mode="json") for job in jobs.values()],
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
