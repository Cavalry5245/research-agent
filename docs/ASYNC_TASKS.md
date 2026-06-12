# Async Tasks

## Current implementation

Phase 3 uses FastAPI `BackgroundTasks` plus the project job store instead of Celery/Redis.

Implemented task types:

- `paper_index`
- `note_generation`
- `paper_comparison`

## Task lifecycle

All tasks use the same lifecycle fields:

- `queued`: accepted but not started
- `running`: executing in the background
- `completed`: finished successfully, `result` is available
- `failed`: execution failed, `error` contains a user-facing message
- `cancelled`: cancellation was requested before completion

Common fields:

- `job_id`
- `job_type`
- `paper_id` or `paper_ids`
- `status`
- `progress`
- `result`
- `error`
- `retry_of`
- `created_at`
- `started_at`
- `completed_at`
- `updated_at`

## API examples

Submit note generation:

```bash
curl -X POST http://localhost:8888/tasks/note/paper_001
```

Submit comparison:

```bash
curl -X POST http://localhost:8888/tasks/compare \
  -H "Content-Type: application/json" \
  -d '{"paper_ids":["paper_001","paper_002"]}'
```

List tasks:

```bash
curl http://localhost:8888/tasks
```

Get status:

```bash
curl http://localhost:8888/tasks/<job_id>
```

Get result:

```bash
curl http://localhost:8888/tasks/<job_id>/result
```

Cancel task:

```bash
curl -X DELETE http://localhost:8888/tasks/<job_id>
```

Retry failed task:

```bash
curl -X POST http://localhost:8888/tasks/<job_id>/retry
```

## Cancellation and retry semantics

Cancellation is cooperative. If a task has not yet started, or checks cancellation before writing the final result, it remains `cancelled`. If the task has already completed, cancellation returns `409`.

Retry is supported for failed note generation and paper comparison tasks. A retry creates a new task with `retry_of` pointing to the original failed task.

## Celery/Redis decision

Celery/Redis is not required for this Phase 3 implementation.

Reasons:

- Current workload is local single-user MVP usage.
- Existing `BackgroundTasks` already covers long-running note, index, and compare jobs.
- `FileJobStore` provides simple persistence without operating Redis.
- Avoiding Celery reduces setup burden and keeps Phase 4/5 velocity high.

When to migrate to Celery/Redis:

- Multiple workers or machines need to process tasks.
- Tasks must survive API process restarts while running.
- Queue prioritization, scheduled retries, or rate limiting becomes necessary.
- Production deployment requires separate web and worker processes.

Migration steps:

1. Move `_run_note_job`, `_run_compare_job`, and index job logic into `app/tasks/paper_tasks.py`.
2. Configure a Celery app with Redis broker/backend.
3. Replace `background_tasks.add_task(...)` calls with Celery `.delay(...)` submissions.
4. Store Celery task ids in `JobStatusResponse.job_id` or a mapping layer.
5. Keep `/tasks/*` API unchanged so UI and clients do not change.
