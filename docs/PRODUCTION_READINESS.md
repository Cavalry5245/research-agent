# Production Readiness

## Phase 3 scope

Phase 3 focuses on lightweight production readiness for the current local MVP:

- Background task submission and status tracking
- Structured JSONL logs
- Request id tracing
- Unified API error responses
- Health checks
- OpenAPI descriptions for task APIs
- Operational documentation

## Completed engineering capabilities

### Background tasks

The system supports asynchronous-style task submission for:

- paper indexing
- note generation
- paper comparison

Task state is exposed through `/tasks/*` and persisted via the existing job store abstraction.

### Observability

All API responses include `X-Request-ID`. API requests and key service operations emit JSONL logs suitable for local analysis and debugging.

### Error handling

HTTP errors return a consistent shape:

```json
{
  "error": "http_error",
  "message": "...",
  "request_id": "...",
  "status_code": 404
}
```

Unhandled exceptions return a safe generic message and are logged server-side.

### Health checks

`/health` reports:

- overall status
- storage writability
- vector store availability
- key config presence

## Decisions

### Celery/Redis

Not introduced in Phase 3. FastAPI `BackgroundTasks` is sufficient for local single-user usage and avoids Redis setup overhead.

### Database/cache

Not introduced in Phase 3. Existing file storage keeps artifacts inspectable and stable for demo workflows.

## Remaining production gaps

- Tasks do not survive process termination while actively running.
- Cancellation is cooperative and cannot interrupt blocking LLM calls mid-flight.
- No multi-user authentication or authorization.
- No deployment-specific process supervision.
- No external metrics backend such as Prometheus or OpenTelemetry.

## Next production steps

Recommended future sequence:

1. Add SQLite/PostgreSQL only when multi-user metadata or Agent memory requires it.
2. Add Celery/Redis when the app needs separate web and worker processes.
3. Add deployment manifests after the API/UI feature set stabilizes.
4. Add OpenTelemetry or Prometheus if deployed as a long-running service.
