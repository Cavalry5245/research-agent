import os
import sys
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.schemas import IndexJobStatusResponse, PaperParseResult, Section
from app.services.paper_status import build_index_job_status
from app.services.vector_backends.json_backend import JsonVectorBackend
from app.services.vector_store import VectorStore


def _make_parsed_result(paper_id: str = "paper_A") -> dict:
    return PaperParseResult(
        paper_id=paper_id,
        title="Paper A",
        abstract="Abstract",
        sections=[
            Section(heading="Method", content="A" * 1200),
            Section(heading="Experiment", content="B" * 900),
        ],
        full_text=("A" * 1200) + ("B" * 900),
    ).model_dump()


class FakeEmbeddingClient:
    def embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class FailingEmbeddingClient:
    def embed_texts(self, texts):
        raise RuntimeError("embedding service unavailable")


def _reset_job_store():
    from app.main import _get_job_store

    _get_job_store().clear()


def test_job_store_list_returns_snapshots_sorted_by_created_at_desc_without_route_sorting():
    from app.main import _get_job_store

    _reset_job_store()
    job_store = _get_job_store()

    older_job = build_index_job_status(
        job_id="job_paper_LIST_OLDER_manual",
        paper_id="paper_LIST_OLDER",
        status="queued",
        created_at="2026-05-13T17:30:00+00:00",
        updated_at="2026-05-13T17:30:00+00:00",
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
    )
    newer_job = build_index_job_status(
        job_id="job_paper_LIST_NEWER_manual",
        paper_id="paper_LIST_NEWER",
        status="queued",
        created_at="2026-05-13T17:31:00+00:00",
        updated_at="2026-05-13T17:31:00+00:00",
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
    )

    job_store.upsert(older_job)
    job_store.upsert(newer_job)

    jobs = job_store.list()

    assert [job.job_id for job in jobs] == [
        "job_paper_LIST_NEWER_manual",
        "job_paper_LIST_OLDER_manual",
    ]


def test_job_store_snapshot_interface_exposes_replaceable_contract_for_future_persistent_store():
    from app.main import _get_job_store

    _reset_job_store()
    job_store = _get_job_store()

    queued_job = build_index_job_status(
        job_id="job_paper_STORE_INTERFACE_queued",
        paper_id="paper_STORE_INTERFACE_queued",
        status="queued",
        created_at="2026-05-13T18:20:00+00:00",
        updated_at="2026-05-13T18:20:00+00:00",
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
    )
    completed_job = build_index_job_status(
        job_id="job_paper_STORE_INTERFACE_completed",
        paper_id="paper_STORE_INTERFACE_completed",
        status="completed",
        created_at="2026-05-13T18:21:00+00:00",
        started_at="2026-05-13T18:21:01+00:00",
        completed_at="2026-05-13T18:21:05+00:00",
        updated_at="2026-05-13T18:21:05+00:00",
        progress=1.0,
        chunks_indexed=3,
        already_indexed=False,
    )

    job_store.upsert(queued_job)
    job_store.upsert(completed_job)

    snapshots = job_store.list()

    assert all(isinstance(job, IndexJobStatusResponse) for job in snapshots)
    assert [job.job_id for job in snapshots] == [
        "job_paper_STORE_INTERFACE_completed",
        "job_paper_STORE_INTERFACE_queued",
    ]

    latest = job_store.get("job_paper_STORE_INTERFACE_completed")
    assert latest is not None
    assert latest.paper_id == "paper_STORE_INTERFACE_completed"
    assert latest.status == "completed"


def test_job_store_protocol_accepts_persistent_style_implementations_for_route_contract(
    monkeypatch,
):
    _reset_job_store()
    client = TestClient(app)

    queued_job = build_index_job_status(
        job_id="job_paper_PROTOCOL_PERSISTENT_queued",
        paper_id="paper_PROTOCOL_PERSISTENT_queued",
        status="queued",
        created_at="2026-05-13T18:54:00+00:00",
        updated_at="2026-05-13T18:54:00+00:00",
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
    )
    completed_job = build_index_job_status(
        job_id="job_paper_PROTOCOL_PERSISTENT_completed",
        paper_id="paper_PROTOCOL_PERSISTENT_completed",
        status="completed",
        created_at="2026-05-13T18:55:00+00:00",
        started_at="2026-05-13T18:55:01+00:00",
        completed_at="2026-05-13T18:55:04+00:00",
        updated_at="2026-05-13T18:55:04+00:00",
        progress=1.0,
        chunks_indexed=2,
        already_indexed=False,
    )

    class _PersistentStyleJobStore:
        def __init__(self, jobs):
            self._jobs = {job.job_id: job for job in jobs}

        def upsert(self, job):
            self._jobs[job.job_id] = job
            return job

        def get(self, job_id):
            return self._jobs.get(job_id)

        def list(self):
            return sorted(
                self._jobs.values(), key=lambda job: job.created_at, reverse=True
            )

        def clear(self):
            self._jobs.clear()

    monkeypatch.setattr(
        "app.main._job_store",
        _PersistentStyleJobStore([queued_job, completed_job]),
    )

    list_response = client.get("/jobs")
    assert list_response.status_code == 200
    assert [job["job_id"] for job in list_response.json()["jobs"]] == [
        "job_paper_PROTOCOL_PERSISTENT_completed",
        "job_paper_PROTOCOL_PERSISTENT_queued",
    ]

    detail_response = client.get("/jobs/job_paper_PROTOCOL_PERSISTENT_completed")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["job_id"] == "job_paper_PROTOCOL_PERSISTENT_completed"
    assert detail["status"] == "completed"
    assert detail["chunks_indexed"] == 2


def test_get_job_store_uses_in_memory_store_by_default_and_can_switch_to_file_store(
    tmp_path, monkeypatch
):
    from app.main import _get_job_store
    from app.services.job_store import FileJobStore, InMemoryJobStore

    _reset_job_store()
    monkeypatch.setattr("app.main._job_store", None)
    monkeypatch.delenv("RESEARCH_AGENT_JOB_STORE_PATH", raising=False)

    default_store = _get_job_store()
    assert isinstance(default_store, InMemoryJobStore)

    monkeypatch.setattr("app.main._job_store", None)
    job_store_path = tmp_path / "configurable_job_store.json"
    monkeypatch.setenv("RESEARCH_AGENT_JOB_STORE_PATH", str(job_store_path))

    file_store = _get_job_store()
    assert isinstance(file_store, FileJobStore)
    assert file_store._path == job_store_path


def test_file_backed_job_store_persists_jobs_across_new_instances(tmp_path):
    from app.services.job_store import FileJobStore

    store_path = tmp_path / "job_store.json"
    first_store = FileJobStore(store_path)

    queued_job = build_index_job_status(
        job_id="job_paper_FILE_STORE_queued",
        paper_id="paper_FILE_STORE_queued",
        status="queued",
        created_at="2026-05-13T19:10:00+00:00",
        updated_at="2026-05-13T19:10:00+00:00",
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
    )
    completed_job = build_index_job_status(
        job_id="job_paper_FILE_STORE_completed",
        paper_id="paper_FILE_STORE_completed",
        status="completed",
        created_at="2026-05-13T19:11:00+00:00",
        started_at="2026-05-13T19:11:01+00:00",
        completed_at="2026-05-13T19:11:05+00:00",
        updated_at="2026-05-13T19:11:05+00:00",
        progress=1.0,
        chunks_indexed=4,
        already_indexed=False,
    )

    first_store.upsert(queued_job)
    first_store.upsert(completed_job)

    reloaded_store = FileJobStore(store_path)

    jobs = reloaded_store.list()
    assert [job.job_id for job in jobs] == [
        "job_paper_FILE_STORE_completed",
        "job_paper_FILE_STORE_queued",
    ]

    latest = reloaded_store.get("job_paper_FILE_STORE_completed")
    assert latest is not None
    assert latest.status == "completed"
    assert latest.completed_at == completed_job.completed_at


def test_index_job_submission_persists_to_file_backed_job_store_when_env_configured(
    tmp_path, monkeypatch
):
    from app.services.job_store import FileJobStore

    _reset_job_store()
    client = TestClient(app)
    store_path = tmp_path / "submitted_job_store.json"

    monkeypatch.setattr("app.main._job_store", None)
    monkeypatch.setenv("RESEARCH_AGENT_JOB_STORE_PATH", str(store_path))
    vector_path = str(tmp_path / "vectors")
    monkeypatch.setattr(
        "app.main._vector_store",
        VectorStore(
            persist_dir=vector_path, backend=JsonVectorBackend(vector_path)
        ),
    )
    monkeypatch.setattr("app.main._embedding_client", FakeEmbeddingClient())
    monkeypatch.setattr(
        "app.main.load_parsed_result", lambda paper_id, _: _make_parsed_result(paper_id)
    )

    response = client.post("/papers/paper_FILE_BACKED_SUBMISSION/index?force=true")

    assert response.status_code == 202
    queued_job = response.json()
    assert queued_job["status"] == "queued"

    reloaded_store = FileJobStore(store_path)
    persisted_job = reloaded_store.get(queued_job["job_id"])
    assert persisted_job is not None
    assert persisted_job.paper_id == "paper_FILE_BACKED_SUBMISSION"
    assert persisted_job.status == "completed"
    assert persisted_job.progress == 1.0
    assert persisted_job.chunks_indexed > 0

    detail_response = client.get(f"/jobs/{queued_job['job_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "completed"


def test_job_routes_accept_file_backed_job_store_contract(monkeypatch, tmp_path):
    from app.services.job_store import FileJobStore

    _reset_job_store()
    client = TestClient(app)
    store_path = tmp_path / "route_job_store.json"
    file_store = FileJobStore(store_path)

    queued_job = build_index_job_status(
        job_id="job_paper_ROUTE_FILE_STORE_queued",
        paper_id="paper_ROUTE_FILE_STORE_queued",
        status="queued",
        created_at="2026-05-13T19:20:00+00:00",
        updated_at="2026-05-13T19:20:00+00:00",
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
    )
    completed_job = build_index_job_status(
        job_id="job_paper_ROUTE_FILE_STORE_completed",
        paper_id="paper_ROUTE_FILE_STORE_completed",
        status="completed",
        created_at="2026-05-13T19:21:00+00:00",
        started_at="2026-05-13T19:21:01+00:00",
        completed_at="2026-05-13T19:21:05+00:00",
        updated_at="2026-05-13T19:21:05+00:00",
        progress=1.0,
        chunks_indexed=5,
        already_indexed=False,
    )

    file_store.upsert(queued_job)
    file_store.upsert(completed_job)
    monkeypatch.setattr("app.main._job_store", file_store)

    list_response = client.get("/jobs")
    assert list_response.status_code == 200
    assert [job["job_id"] for job in list_response.json()["jobs"]] == [
        "job_paper_ROUTE_FILE_STORE_completed",
        "job_paper_ROUTE_FILE_STORE_queued",
    ]

    detail_response = client.get("/jobs/job_paper_ROUTE_FILE_STORE_completed")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["paper_id"] == "paper_ROUTE_FILE_STORE_completed"
    assert detail["chunks_indexed"] == 5


def test_index_job_status_endpoint_returns_404_for_unknown_job_id():
    _reset_job_store()
    client = TestClient(app)

    response = client.get("/jobs/job_does_not_exist")

    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "任务 job_does_not_exist 不存在"
    assert body["status_code"] == 404


def test_index_job_status_endpoint_returns_empty_list_when_no_jobs_exist():
    _reset_job_store()
    client = TestClient(app)

    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == {"count": 0, "jobs": []}


def test_build_index_job_status_rejects_progress_outside_0_to_1_range():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_BAD_PROGRESS_manual",
            paper_id="paper_BAD_PROGRESS",
            status="queued",
            created_at="2026-05-13T06:00:00+00:00",
            updated_at="2026-05-13T06:00:00+00:00",
            progress=1.5,
            chunks_indexed=0,
            already_indexed=False,
        )

    assert "progress" in str(exc_info.value)
    assert "less than or equal to 1" in str(exc_info.value)


def test_build_index_job_status_rejects_invalid_status_value():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_BAD_STATUS_manual",
            paper_id="paper_BAD_STATUS",
            status="paused",
            created_at="2026-05-13T06:05:00+00:00",
            updated_at="2026-05-13T06:05:00+00:00",
            progress=0.5,
            chunks_indexed=2,
            already_indexed=False,
        )

    assert "status" in str(exc_info.value)
    assert "queued" in str(exc_info.value)
    assert "running" in str(exc_info.value)
    assert "completed" in str(exc_info.value)
    assert "failed" in str(exc_info.value)


def test_build_index_job_status_rejects_invalid_created_at_datetime_string():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_BAD_CREATED_AT_manual",
            paper_id="paper_BAD_CREATED_AT",
            status="queued",
            created_at="not-a-datetime",
            updated_at="2026-05-13T06:10:00+00:00",
            progress=0.0,
            chunks_indexed=0,
            already_indexed=False,
        )

    assert "created_at" in str(exc_info.value)
    assert "valid datetime" in str(exc_info.value)


def test_build_index_job_status_rejects_started_at_before_created_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_STARTED_BEFORE_CREATED_AT_manual",
            paper_id="paper_STARTED_BEFORE_CREATED_AT",
            status="running",
            created_at="2026-05-13T17:00:00+00:00",
            started_at="2026-05-13T16:59:59+00:00",
            completed_at=None,
            updated_at="2026-05-13T17:00:05+00:00",
            progress=0.25,
            chunks_indexed=1,
            already_indexed=False,
        )

    assert "started_at" in str(exc_info.value)
    assert "created_at" in str(exc_info.value)


def test_build_index_job_status_rejects_updated_at_before_created_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_UPDATED_BEFORE_CREATED_AT_manual",
            paper_id="paper_UPDATED_BEFORE_CREATED_AT",
            status="queued",
            created_at="2026-05-13T17:10:00+00:00",
            started_at=None,
            completed_at=None,
            updated_at="2026-05-13T17:09:59+00:00",
            progress=0.0,
            chunks_indexed=0,
            already_indexed=False,
        )

    assert "updated_at" in str(exc_info.value)
    assert "created_at" in str(exc_info.value)


def test_build_index_job_status_accepts_running_status_with_started_at_not_before_created_at():
    job = build_index_job_status(
        job_id="job_paper_RUNNING_TIME_ORDER_OK_manual",
        paper_id="paper_RUNNING_TIME_ORDER_OK",
        status="running",
        created_at="2026-05-13T17:20:00+00:00",
        started_at="2026-05-13T17:20:01+00:00",
        completed_at=None,
        updated_at="2026-05-13T17:20:05+00:00",
        progress=0.5,
        chunks_indexed=2,
        already_indexed=False,
    )

    assert job.status == "running"
    assert job.started_at is not None
    assert job.started_at >= job.created_at
    assert job.updated_at >= job.created_at


def test_build_index_job_status_rejects_completed_status_without_completed_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_MISSING_COMPLETED_AT_manual",
            paper_id="paper_MISSING_COMPLETED_AT",
            status="completed",
            created_at="2026-05-13T08:00:00+00:00",
            started_at="2026-05-13T08:00:02+00:00",
            completed_at=None,
            updated_at="2026-05-13T08:00:05+00:00",
            progress=1.0,
            chunks_indexed=3,
            already_indexed=False,
        )

    assert "completed_at" in str(exc_info.value)
    assert "completed" in str(exc_info.value)


def test_build_index_job_status_rejects_failed_status_with_completed_at_without_started_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_FAILED_WITHOUT_STARTED_AT_manual",
            paper_id="paper_FAILED_WITHOUT_STARTED_AT",
            status="failed",
            created_at="2026-05-13T09:00:00+00:00",
            started_at=None,
            completed_at="2026-05-13T09:00:05+00:00",
            updated_at="2026-05-13T09:00:05+00:00",
            progress=0.25,
            chunks_indexed=0,
            already_indexed=False,
            error="embedding service unavailable",
        )

    assert "failed" in str(exc_info.value)
    assert "completed_at" in str(exc_info.value)


def test_build_index_job_status_rejects_failed_status_without_started_or_completed_at_when_progress_is_nonzero():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_FAILED_PROGRESS_WITHOUT_START_manual",
            paper_id="paper_FAILED_PROGRESS_WITHOUT_START",
            status="failed",
            created_at="2026-05-13T09:30:00+00:00",
            started_at=None,
            completed_at=None,
            updated_at="2026-05-13T09:30:05+00:00",
            progress=0.25,
            chunks_indexed=0,
            already_indexed=False,
            error="embedding service unavailable",
        )

    assert "failed" in str(exc_info.value)
    assert "started_at" in str(exc_info.value)


def test_build_index_job_status_rejects_failed_status_with_zero_progress_if_started_at_is_present_without_completed_at_and_without_error():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_FAILED_ZERO_PROGRESS_WITH_STARTED_AT_manual",
            paper_id="paper_FAILED_ZERO_PROGRESS_WITH_STARTED_AT",
            status="failed",
            created_at="2026-05-13T10:00:00+00:00",
            started_at="2026-05-13T10:00:01+00:00",
            completed_at=None,
            updated_at="2026-05-13T10:00:05+00:00",
            progress=0.0,
            chunks_indexed=0,
            already_indexed=False,
            error=None,
        )

    assert "failed" in str(exc_info.value)
    assert "progress" in str(exc_info.value)
    assert "started_at" in str(exc_info.value)


def test_build_index_job_status_rejects_queued_status_with_started_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_QUEUED_WITH_STARTED_AT_manual",
            paper_id="paper_QUEUED_WITH_STARTED_AT",
            status="queued",
            created_at="2026-05-13T10:45:00+00:00",
            started_at="2026-05-13T10:45:01+00:00",
            completed_at=None,
            updated_at="2026-05-13T10:45:05+00:00",
            progress=0.0,
            chunks_indexed=0,
            already_indexed=False,
        )

    assert "queued" in str(exc_info.value)
    assert "started_at" in str(exc_info.value)


def test_build_index_job_status_rejects_running_status_without_started_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_RUNNING_WITHOUT_STARTED_AT_manual",
            paper_id="paper_RUNNING_WITHOUT_STARTED_AT",
            status="running",
            created_at="2026-05-13T11:00:00+00:00",
            started_at=None,
            completed_at=None,
            updated_at="2026-05-13T11:00:05+00:00",
            progress=0.25,
            chunks_indexed=0,
            already_indexed=False,
        )

    assert "running" in str(exc_info.value)
    assert "started_at" in str(exc_info.value)


def test_build_index_job_status_rejects_running_status_with_completed_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_RUNNING_WITH_COMPLETED_AT_manual",
            paper_id="paper_RUNNING_WITH_COMPLETED_AT",
            status="running",
            created_at="2026-05-13T12:00:00+00:00",
            started_at="2026-05-13T12:00:01+00:00",
            completed_at="2026-05-13T12:00:05+00:00",
            updated_at="2026-05-13T12:00:05+00:00",
            progress=0.5,
            chunks_indexed=1,
            already_indexed=False,
        )

    assert "running" in str(exc_info.value)
    assert "completed_at" in str(exc_info.value)


def test_build_index_job_status_rejects_failed_status_with_completed_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_FAILED_WITH_COMPLETED_AT_manual",
            paper_id="paper_FAILED_WITH_COMPLETED_AT",
            status="failed",
            created_at="2026-05-13T12:45:00+00:00",
            started_at="2026-05-13T12:45:01+00:00",
            completed_at="2026-05-13T12:45:05+00:00",
            updated_at="2026-05-13T12:45:05+00:00",
            progress=0.5,
            chunks_indexed=1,
            already_indexed=False,
            error="embedding service unavailable",
        )

    assert "failed" in str(exc_info.value)
    assert "completed_at" in str(exc_info.value)


def test_build_index_job_status_accepts_completed_status_with_started_and_completed_at():
    status = build_index_job_status(
        job_id="job_paper_COMPLETED_WITH_TIMESTAMPS_manual",
        paper_id="paper_COMPLETED_WITH_TIMESTAMPS",
        status="completed",
        created_at="2026-05-13T16:40:00+00:00",
        started_at="2026-05-13T16:40:01+00:00",
        completed_at="2026-05-13T16:40:05+00:00",
        updated_at="2026-05-13T16:40:05+00:00",
        progress=1.0,
        chunks_indexed=3,
        already_indexed=False,
    )

    assert status.status == "completed"
    assert status.started_at is not None
    assert status.completed_at is not None
    assert status.started_at.isoformat() == "2026-05-13T16:40:01+00:00"
    assert status.completed_at.isoformat() == "2026-05-13T16:40:05+00:00"


def test_build_index_job_status_rejects_completed_status_with_completed_at_before_started_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_COMPLETED_BACKWARDS_TIMESTAMPS_manual",
            paper_id="paper_COMPLETED_BACKWARDS_TIMESTAMPS",
            status="completed",
            created_at="2026-05-13T16:41:00+00:00",
            started_at="2026-05-13T16:41:05+00:00",
            completed_at="2026-05-13T16:41:01+00:00",
            updated_at="2026-05-13T16:41:05+00:00",
            progress=1.0,
            chunks_indexed=3,
            already_indexed=False,
        )

    assert "completed_at" in str(exc_info.value)
    assert "started_at" in str(exc_info.value)


def test_build_index_job_status_rejects_completed_status_with_updated_at_before_completed_at():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_COMPLETED_UPDATED_BEFORE_COMPLETED_manual",
            paper_id="paper_COMPLETED_UPDATED_BEFORE_COMPLETED",
            status="completed",
            created_at="2026-05-13T16:42:00+00:00",
            started_at="2026-05-13T16:42:01+00:00",
            completed_at="2026-05-13T16:42:05+00:00",
            updated_at="2026-05-13T16:42:04+00:00",
            progress=1.0,
            chunks_indexed=3,
            already_indexed=False,
        )

    assert "updated_at" in str(exc_info.value)
    assert "completed_at" in str(exc_info.value)


def test_build_index_job_status_rejects_failed_status_with_error_but_without_started_at_even_when_progress_is_zero():
    with pytest.raises(ValidationError) as exc_info:
        build_index_job_status(
            job_id="job_paper_FAILED_WITH_ERROR_ZERO_PROGRESS_WITHOUT_STARTED_AT_manual",
            paper_id="paper_FAILED_WITH_ERROR_ZERO_PROGRESS_WITHOUT_STARTED_AT",
            status="failed",
            created_at="2026-05-13T14:20:00+00:00",
            started_at=None,
            completed_at=None,
            updated_at="2026-05-13T14:20:05+00:00",
            progress=0.0,
            chunks_indexed=0,
            already_indexed=False,
            error="论文内容为空，无法生成索引块",
        )

    assert "failed" in str(exc_info.value)
    assert "started_at" in str(exc_info.value)


def test_index_job_status_endpoint_preserves_zero_progress_failed_job_with_error_and_started_at_for_empty_chunks():
    _reset_job_store()
    client = TestClient(app)

    short_parsed = PaperParseResult(
        paper_id="paper_EMPTY_STARTED_AT",
        title="Paper Empty",
        abstract="太短了",
        sections=[Section(heading="Intro", content="太短了")],
        full_text="太短了",
    ).model_dump()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=short_parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            queued = client.post("/papers/paper_EMPTY_STARTED_AT/index")
            assert queued.status_code == 202
            job_id = queued.json()["job_id"]

            response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["progress"] == 0.0
    assert body["error"] == "论文内容为空，无法生成索引块"
    assert body["started_at"] is not None
    assert body["completed_at"] is None


def test_build_index_job_status_accepts_failed_status_with_error_and_started_at_when_progress_is_zero():
    job = build_index_job_status(
        job_id="job_paper_FAILED_WITH_ERROR_AND_STARTED_AT_ZERO_PROGRESS_manual",
        paper_id="paper_FAILED_WITH_ERROR_AND_STARTED_AT_ZERO_PROGRESS",
        status="failed",
        created_at="2026-05-13T14:25:00+00:00",
        started_at="2026-05-13T14:25:01+00:00",
        completed_at=None,
        updated_at="2026-05-13T14:25:05+00:00",
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
        error="论文内容为空，无法生成索引块",
    )

    assert job.status == "failed"
    assert job.progress == 0.0
    assert job.started_at is not None
    assert job.completed_at is None
    assert job.error == "论文内容为空，无法生成索引块"


def test_build_index_job_status_accepts_failed_status_with_error_and_started_at_when_progress_is_nonzero():
    job = build_index_job_status(
        job_id="job_paper_FAILED_WITH_ERROR_AND_STARTED_AT_manual",
        paper_id="paper_FAILED_WITH_ERROR_AND_STARTED_AT",
        status="failed",
        created_at="2026-05-13T13:25:00+00:00",
        started_at="2026-05-13T13:25:01+00:00",
        completed_at=None,
        updated_at="2026-05-13T13:25:05+00:00",
        progress=0.5,
        chunks_indexed=1,
        already_indexed=False,
        error="embedding service unavailable",
    )

    assert job.status == "failed"
    assert job.started_at is not None
    assert job.completed_at is None
    assert job.error == "embedding service unavailable"


def test_build_index_job_status_tracks_started_and_completed_timestamps_when_provided():
    job = build_index_job_status(
        job_id="job_paper_TIMESTAMPS_manual",
        paper_id="paper_TIMESTAMPS",
        status="completed",
        created_at="2026-05-13T07:00:00+00:00",
        started_at="2026-05-13T07:00:02+00:00",
        completed_at="2026-05-13T07:00:05+00:00",
        updated_at="2026-05-13T07:00:05+00:00",
        progress=1.0,
        chunks_indexed=3,
        already_indexed=False,
    )

    assert job.started_at.isoformat() == "2026-05-13T07:00:02+00:00"
    assert job.completed_at.isoformat() == "2026-05-13T07:00:05+00:00"


def test_index_job_list_endpoint_returns_typed_jobs_envelope_schema():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_SCHEMA_DONE")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            completed = client.post("/papers/paper_SCHEMA_DONE/index")
            assert completed.status_code == 202
            completed_job_id = completed.json()["job_id"]

        from app.main import _get_job_store

        queued_job_id = "job_paper_SCHEMA_QUEUED_manual"
        _get_job_store().upsert(
            build_index_job_status(
                job_id=queued_job_id,
                paper_id="paper_SCHEMA_QUEUED",
                status="queued",
                created_at="2026-05-13T05:30:00+00:00",
                updated_at="2026-05-13T05:30:00+00:00",
                progress=0.0,
                chunks_indexed=0,
                already_indexed=False,
            )
        )

        response = client.get("/jobs")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"count", "jobs"}
    assert body["count"] == 2
    assert isinstance(body["jobs"], list)
    assert [job["job_id"] for job in body["jobs"]] == [completed_job_id, queued_job_id]

    completed_job = body["jobs"][0]
    queued_job = body["jobs"][1]

    assert set(queued_job.keys()) == {
        "job_id",
        "job_type",
        "paper_id",
        "status",
        "progress",
        "chunks_indexed",
        "already_indexed",
        "parse_seconds",
        "chunk_seconds",
        "embedding_seconds",
        "persist_seconds",
        "total_seconds",
        "created_at",
        "started_at",
        "completed_at",
        "updated_at",
        "error",
    }
    assert queued_job["job_id"] == queued_job_id
    assert queued_job["job_type"] == "paper_index"
    assert queued_job["paper_id"] == "paper_SCHEMA_QUEUED"
    assert queued_job["status"] == "queued"
    assert queued_job["progress"] == 0.0
    assert queued_job["chunks_indexed"] == 0
    assert queued_job["already_indexed"] is False
    assert queued_job["error"] is None
    assert queued_job["started_at"] is None
    assert queued_job["completed_at"] is None

    assert completed_job["job_id"] == completed_job_id
    assert completed_job["job_type"] == "paper_index"
    assert completed_job["paper_id"] == "paper_SCHEMA_DONE"
    assert completed_job["status"] == "completed"
    assert completed_job["progress"] == 1.0
    assert completed_job["chunks_indexed"] > 0
    assert completed_job["already_indexed"] is False
    assert completed_job["error"] is None
    assert completed_job["started_at"] is not None
    assert completed_job["completed_at"] is not None


def test_index_job_list_endpoint_returns_all_current_job_states_sorted_by_created_at_desc():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed_done = _make_parsed_result("paper_LIST_DONE")

        def _load_parsed_result(paper_id: str, _metadata_dir: str):
            if paper_id == "paper_LIST_DONE":
                return parsed_done
            if paper_id == "paper_LIST_FAIL":
                raise FileNotFoundError(
                    "论文 paper_LIST_FAIL 的解析结果不存在，请先解析 PDF"
                )
            raise AssertionError(f"unexpected paper_id: {paper_id}")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", side_effect=_load_parsed_result
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            completed = client.post("/papers/paper_LIST_DONE/index")
            assert completed.status_code == 202
            completed_job_id = completed.json()["job_id"]

            failed = client.post("/papers/paper_LIST_FAIL/index")
            assert failed.status_code == 202
            failed_job_id = failed.json()["job_id"]

        from app.main import _get_job_store
        from app.services.paper_status import build_index_job_status

        queued_job_id = "job_paper_LIST_QUEUED_manual"
        running_job_id = "job_paper_LIST_RUNNING_manual"

        _get_job_store().upsert(
            build_index_job_status(
                job_id=queued_job_id,
                paper_id="paper_LIST_QUEUED",
                status="queued",
                created_at="2026-05-13T04:15:00+00:00",
                updated_at="2026-05-13T04:15:00+00:00",
                progress=0.0,
                chunks_indexed=0,
                already_indexed=False,
            )
        )
        _get_job_store().upsert(
            build_index_job_status(
                job_id=running_job_id,
                paper_id="paper_LIST_RUNNING",
                status="running",
                created_at="2026-05-13T04:10:00+00:00",
                started_at="2026-05-13T04:10:01+00:00",
                updated_at="2026-05-13T04:10:01+00:00",
                progress=0.25,
                chunks_indexed=0,
                already_indexed=False,
                parse_seconds=0.001,
                chunk_seconds=0.002,
            )
        )

        response = client.get("/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4
    job_ids = [job["job_id"] for job in body["jobs"]]
    assert set(job_ids) == {
        queued_job_id,
        running_job_id,
        failed_job_id,
        completed_job_id,
    }

    queued_job = next(job for job in body["jobs"] if job["job_id"] == queued_job_id)
    running_job = next(job for job in body["jobs"] if job["job_id"] == running_job_id)
    failed_job = next(job for job in body["jobs"] if job["job_id"] == failed_job_id)
    completed_job = next(
        job for job in body["jobs"] if job["job_id"] == completed_job_id
    )

    assert queued_job["created_at"] > running_job["created_at"]
    assert failed_job["created_at"] > completed_job["created_at"]
    assert queued_job["status"] == "queued"
    assert running_job["status"] == "running"
    assert failed_job["status"] == "failed"
    assert completed_job["status"] == "completed"
    assert queued_job["progress"] == 0.0
    assert queued_job["error"] is None
    assert running_job["progress"] == 0.25
    assert running_job["error"] is None
    assert failed_job["error"] == "论文 paper_LIST_FAIL 的解析结果不存在，请先解析 PDF"
    assert completed_job["error"] is None
    assert [job["created_at"] for job in body["jobs"]] == sorted(
        [job["created_at"] for job in body["jobs"]], reverse=True
    )


def test_index_job_list_endpoint_returns_failed_and_completed_jobs_sorted_by_created_at_desc():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed_ok = _make_parsed_result("paper_LIST_OK")

        def _load_parsed_result(paper_id: str, _metadata_dir: str):
            if paper_id == "paper_LIST_OK":
                return parsed_ok
            if paper_id == "paper_LIST_FAIL":
                raise FileNotFoundError(
                    "论文 paper_LIST_FAIL 的解析结果不存在，请先解析 PDF"
                )
            raise AssertionError(f"unexpected paper_id: {paper_id}")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", side_effect=_load_parsed_result
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            first = client.post("/papers/paper_LIST_OK/index")
            assert first.status_code == 202
            first_job_id = first.json()["job_id"]

            second = client.post("/papers/paper_LIST_FAIL/index")
            assert second.status_code == 202
            second_job_id = second.json()["job_id"]

            response = client.get("/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [job["job_id"] for job in body["jobs"]] == [second_job_id, first_job_id]
    assert [job["paper_id"] for job in body["jobs"]] == [
        "paper_LIST_FAIL",
        "paper_LIST_OK",
    ]
    assert [job["status"] for job in body["jobs"]] == ["failed", "completed"]
    assert (
        body["jobs"][0]["error"]
        == "论文 paper_LIST_FAIL 的解析结果不存在，请先解析 PDF"
    )
    assert body["jobs"][1]["error"] is None
    assert body["jobs"][0]["created_at"] >= body["jobs"][1]["created_at"]


def test_job_status_disappears_after_job_store_reset():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_RESET")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            created = client.post("/papers/paper_RESET/index")
            assert created.status_code == 202
            job_id = created.json()["job_id"]

            existing = client.get(f"/jobs/{job_id}")
            assert existing.status_code == 200
            assert existing.json()["status"] == "completed"

    _reset_job_store()
    missing = client.get(f"/jobs/{job_id}")

    assert missing.status_code == 404
    body = missing.json()
    assert body["message"] == f"任务 {job_id} 不存在"
    assert body["status_code"] == 404


def test_unknown_job_lookup_does_not_leak_jobs_from_previous_tests():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_ISO")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            created = client.post("/papers/paper_ISO/index")
            assert created.status_code == 202

    _reset_job_store()
    missing = client.get("/jobs/job_paper_ISO_ghost")

    assert missing.status_code == 404
    body = missing.json()
    assert body["message"] == "任务 job_paper_ISO_ghost 不存在"
    assert body["status_code"] == 404


def test_index_endpoint_returns_job_status_and_avoids_repeat_indexing():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_A")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            first = client.post("/papers/paper_A/index")
            assert first.status_code == 202
            body1 = first.json()
            assert body1["status"] == "queued"
            assert body1["job_id"].startswith("job_paper_A_")
            assert body1["paper_id"] == "paper_A"
            assert body1["job_type"] == "paper_index"
            assert body1["progress"] == 0.0
            assert body1["chunks_indexed"] == 0
            assert body1["already_indexed"] is False
            assert body1["embedding_seconds"] == 0.0
            assert body1["persist_seconds"] == 0.0
            assert body1["total_seconds"] == 0.0
            assert body1["error"] is None

            first_status = client.get(f"/jobs/{body1['job_id']}")
            assert first_status.status_code == 200
            first_status_body = first_status.json()
            assert first_status_body["status"] == "completed"
            assert first_status_body["progress"] == 1.0
            assert first_status_body["chunks_indexed"] > 0
            first_chunks = first_status_body["chunks_indexed"]

            second = client.post("/papers/paper_A/index")
            assert second.status_code == 200
            body2 = second.json()
            assert body2["status"] == "completed"
            assert body2["already_indexed"] is True
            assert body2["chunks_indexed"] == first_chunks
            assert body2["job_id"] != body1["job_id"]

            forced = client.post("/papers/paper_A/index?force=true")
            assert forced.status_code == 202
            body3 = forced.json()
            assert body3["status"] == "queued"
            assert body3["already_indexed"] is False
            assert body3["job_id"].startswith("job_paper_A_")

            forced_status = client.get(f"/jobs/{body3['job_id']}")
            assert forced_status.status_code == 200
            forced_status_body = forced_status.json()
            assert forced_status_body["status"] == "completed"
            assert forced_status_body["progress"] == 1.0
            assert forced_status_body["chunks_indexed"] == first_chunks


def test_index_job_status_endpoint_returns_latest_job_for_paper():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_A")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            created = client.post("/papers/paper_A/index")
            assert created.status_code == 202
            job_id = created.json()["job_id"]

            status_resp = client.get(f"/jobs/{job_id}")
            assert status_resp.status_code == 200
            status_body = status_resp.json()
            assert status_body["job_id"] == job_id
            assert status_body["paper_id"] == "paper_A"
            assert status_body["status"] == "completed"
            assert status_body["job_type"] == "paper_index"
            assert status_body["progress"] == 1.0


def test_index_endpoint_enqueues_background_job_and_initial_status_is_queued():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_BG")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            response = client.post("/papers/paper_BG/index")
            assert response.status_code == 202
            body = response.json()
            assert body["status"] == "queued"
            assert body["paper_id"] == "paper_BG"
            assert body["job_type"] == "paper_index"
            assert body["progress"] == 0.0
            assert body["chunks_indexed"] == 0
            assert body["already_indexed"] is False
            assert body["error"] is None

            status_resp = client.get(f"/jobs/{body['job_id']}")
            assert status_resp.status_code == 200
            status_body = status_resp.json()
            assert status_body["job_id"] == body["job_id"]
            assert status_body["status"] == "completed"
            assert status_body["paper_id"] == "paper_BG"
            assert status_body["progress"] == 1.0
            assert status_body["chunks_indexed"] > 0


def test_index_job_status_endpoint_returns_failed_job_when_parsed_metadata_missing():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result",
            side_effect=FileNotFoundError(
                "论文 paper_MISSING 的解析结果不存在，请先解析 PDF"
            ),
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            response = client.post("/papers/paper_MISSING/index")
            assert response.status_code == 202
            body = response.json()
            assert body["status"] == "queued"
            assert body["paper_id"] == "paper_MISSING"
            assert body["progress"] == 0.0
            assert body["chunks_indexed"] == 0
            assert body["error"] is None

            status_resp = client.get(f"/jobs/{body['job_id']}")
            assert status_resp.status_code == 200
            status_body = status_resp.json()
            assert status_body["job_id"] == body["job_id"]
            assert status_body["paper_id"] == "paper_MISSING"
            assert status_body["status"] == "failed"
            assert status_body["progress"] == 0.0
            assert status_body["chunks_indexed"] == 0
            assert status_body["parse_seconds"] == 0.0
            assert status_body["chunk_seconds"] == 0.0
            assert status_body["embedding_seconds"] == 0.0
            assert status_body["persist_seconds"] == 0.0
            assert (
                status_body["error"]
                == "论文 paper_MISSING 的解析结果不存在，请先解析 PDF"
            )
            assert status_body["updated_at"] >= status_body["created_at"]


def test_index_job_status_endpoint_returns_failed_job_when_parsed_content_produces_no_chunks():
    _reset_job_store()
    client = TestClient(app)

    parsed = PaperParseResult(
        paper_id="paper_EMPTY",
        title="Paper Empty",
        abstract="短摘要",
        sections=[Section(heading="Method", content="太短了")],
        full_text="太短了",
    ).model_dump()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            response = client.post("/papers/paper_EMPTY/index")
            assert response.status_code == 202
            body = response.json()
            assert body["status"] == "queued"
            assert body["paper_id"] == "paper_EMPTY"
            assert body["progress"] == 0.0
            assert body["chunks_indexed"] == 0

            status_resp = client.get(f"/jobs/{body['job_id']}")
            assert status_resp.status_code == 200
            status_body = status_resp.json()
            assert status_body["job_id"] == body["job_id"]
            assert status_body["paper_id"] == "paper_EMPTY"
            assert status_body["status"] == "failed"
            assert status_body["progress"] == 0.0
            assert status_body["chunks_indexed"] == 0
            assert status_body["parse_seconds"] >= 0.0
            assert status_body["chunk_seconds"] >= 0.0
            assert status_body["embedding_seconds"] == 0.0
            assert status_body["persist_seconds"] == 0.0
            assert status_body["error"] == "论文内容为空，无法生成索引块"
            assert status_body["updated_at"] >= status_body["created_at"]


def test_index_job_status_endpoint_preserves_started_at_when_job_fails_after_entering_running():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_FAIL_STARTED_AT")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch(
            "app.main._get_embedding_client", return_value=FailingEmbeddingClient()
        ):
            response = client.post("/papers/paper_FAIL_STARTED_AT/index")
            assert response.status_code == 202
            body = response.json()
            assert body["status"] == "queued"
            assert body["paper_id"] == "paper_FAIL_STARTED_AT"

            status_resp = client.get(f"/jobs/{body['job_id']}")
            assert status_resp.status_code == 200
            status_body = status_resp.json()
            assert status_body["job_id"] == body["job_id"]
            assert status_body["paper_id"] == "paper_FAIL_STARTED_AT"
            assert status_body["status"] == "failed"
            assert status_body["progress"] == 0.25
            assert status_body["chunks_indexed"] == 0
            assert status_body["started_at"] is not None
            assert status_body["completed_at"] is None
            assert status_body["updated_at"] >= status_body["started_at"]
            assert status_body["error"] == "embedding service unavailable"
            assert status_body["total_seconds"] >= 0.0


def test_index_job_status_endpoint_returns_failed_job_when_embedding_raises():
    _reset_job_store()
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        parsed = _make_parsed_result("paper_FAIL")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch(
            "app.main._get_embedding_client", return_value=FailingEmbeddingClient()
        ):
            response = client.post("/papers/paper_FAIL/index")
            assert response.status_code == 202
            body = response.json()
            assert body["status"] == "queued"
            assert body["paper_id"] == "paper_FAIL"

            status_resp = client.get(f"/jobs/{body['job_id']}")
            assert status_resp.status_code == 200
            status_body = status_resp.json()
            assert status_body["job_id"] == body["job_id"]
            assert status_body["paper_id"] == "paper_FAIL"
            assert status_body["status"] == "failed"
            assert status_body["progress"] == 0.25
            assert status_body["chunks_indexed"] == 0
            assert status_body["error"] == "embedding service unavailable"
            assert status_body["total_seconds"] >= 0.0
            assert status_body["updated_at"] >= status_body["created_at"]
