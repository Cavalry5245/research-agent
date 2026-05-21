# Logging Guide

## Overview

Phase 3 adds structured JSONL logging and request tracing for API and service-level debugging.

Default log path:

```text
app/storage/logs/app.jsonl
```

Override with:

```bash
export RESEARCH_AGENT_LOG_PATH=/path/to/app.jsonl
```

## Log format

Each log line is a JSON object with at least:

- `timestamp`
- `level`
- `event`
- `logger`

Business fields are passed with the `ra_` prefix in Python logging `extra` and emitted without the prefix.

Example:

```json
{
  "timestamp": "2026-05-21T00:00:00+00:00",
  "level": "info",
  "event": "api_request",
  "logger": "app.middleware.tracing",
  "request_id": "...",
  "method": "GET",
  "path": "/health",
  "status_code": 200,
  "duration_ms": 12.3
}
```

## Request tracing

All API responses include:

```text
X-Request-ID: <uuid-or-client-provided-id>
```

If the client sends `X-Request-ID`, the server preserves it. Otherwise the middleware generates a UUID.

Use this id to correlate:

- API request logs
- error responses
- user bug reports
- server-side exception logs

## Service events

Current service events include:

- `api_request`
- `index_job_completed`
- `index_job_failed`
- `qa_completed`
- `note_generated`
- `comparison_completed`
- `agent_execute_completed`
- `unhandled_exception`

## Log analysis

Generate a report:

```bash
python -m app.analytics.log_analyzer \
  --log-file app/storage/logs/app.jsonl \
  --output app/analytics/reports/log_analysis.md
```

The report includes:

- total log count
- API request count
- API error rate
- endpoint call counts
- P50/P95 endpoint latency
- service event counts

## Troubleshooting flow

1. Ask the user for the `X-Request-ID` from the failed response.
2. Search the JSONL log for that `request_id`.
3. Check the API status code and duration.
4. If the error came from a background task, inspect `/tasks/<job_id>`.
5. If logs show `unhandled_exception`, use the stored path and request id to reproduce locally.
