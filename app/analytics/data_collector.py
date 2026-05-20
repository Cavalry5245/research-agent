"""AnalyticsCollector — lightweight JSONL event sink for QA/comparison/indexing/failure events.

Design constraints:
- No external dependencies beyond stdlib + pydantic (already in core)
- Append-only JSONL persistence (atomic per-line write)
- Thread-safe via simple lock
- Single-line write cost target < 1ms so main flow stays unaffected
- Mirrors the FileJobStore pattern (app/services/job_store.py)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from app.services.job_store import utc_now_iso

logger = logging.getLogger(__name__)

DEFAULT_EVENTS_PATH = Path("app/storage/analytics/events.jsonl")
DEFAULT_FAILURES_PATH = Path("app/storage/analytics/failures.jsonl")

EVENT_TYPES = {"qa", "comparison", "indexing", "note", "failure"}


@dataclass
class AnalyticsEvent:
    event_type: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AnalyticsCollector:
    def __init__(
        self,
        events_path: str | Path = DEFAULT_EVENTS_PATH,
        failures_path: str | Path = DEFAULT_FAILURES_PATH,
    ) -> None:
        self._events_path = Path(events_path)
        self._failures_path = Path(failures_path)
        self._events_path.parent.mkdir(parents=True, exist_ok=True)
        self._failures_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _append(self, path: Path, event: AnalyticsEvent) -> None:
        line = event.to_json() + "\n"
        with self._lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)

    def log_event(self, event_type: str, **payload: Any) -> AnalyticsEvent:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event_type '{event_type}'. Expected one of {sorted(EVENT_TYPES)}")
        event = AnalyticsEvent(event_type=event_type, timestamp=utc_now_iso(), payload=payload)
        try:
            self._append(self._events_path, event)
        except OSError as exc:
            logger.warning("AnalyticsCollector failed to persist event: %s", exc)
        return event

    def log_qa_request(
        self,
        paper_id: str | None,
        question: str,
        answer: str,
        retrieval_time: float,
        llm_time: float,
        sources_count: int = 0,
        top_k: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AnalyticsEvent:
        payload = {
            "paper_id": paper_id,
            "question": question,
            "answer_length": len(answer or ""),
            "retrieval_time": retrieval_time,
            "llm_time": llm_time,
            "total_time": retrieval_time + llm_time,
            "sources_count": sources_count,
            "top_k": top_k,
        }
        if extra:
            payload.update(extra)
        return self.log_event("qa", **payload)

    def log_comparison(
        self,
        paper_ids: list[str],
        generation_time: float,
        result_length: int,
        aspects_count: int = 0,
        extra: dict[str, Any] | None = None,
    ) -> AnalyticsEvent:
        payload = {
            "paper_ids": paper_ids,
            "paper_count": len(paper_ids),
            "generation_time": generation_time,
            "result_length": result_length,
            "aspects_count": aspects_count,
        }
        if extra:
            payload.update(extra)
        return self.log_event("comparison", **payload)

    def log_indexing(
        self,
        paper_id: str,
        chunk_count: int,
        embedding_time: float,
        parse_time: float = 0.0,
        persist_time: float = 0.0,
        extra: dict[str, Any] | None = None,
    ) -> AnalyticsEvent:
        payload = {
            "paper_id": paper_id,
            "chunk_count": chunk_count,
            "embedding_time": embedding_time,
            "parse_time": parse_time,
            "persist_time": persist_time,
            "total_time": embedding_time + parse_time + persist_time,
        }
        if extra:
            payload.update(extra)
        return self.log_event("indexing", **payload)

    def log_note(
        self,
        paper_id: str,
        llm_time: float,
        content_length: int,
        extra: dict[str, Any] | None = None,
    ) -> AnalyticsEvent:
        payload = {
            "paper_id": paper_id,
            "llm_time": llm_time,
            "content_length": content_length,
        }
        if extra:
            payload.update(extra)
        return self.log_event("note", **payload)

    def log_failure(
        self,
        failure_type: str,
        context: dict[str, Any],
        reason: str | None = None,
    ) -> AnalyticsEvent:
        payload = {"failure_type": failure_type, "reason": reason, "context": context}
        event = AnalyticsEvent(event_type="failure", timestamp=utc_now_iso(), payload=payload)
        try:
            self._append(self._failures_path, event)
        except OSError as exc:
            logger.warning("AnalyticsCollector failed to persist failure: %s", exc)
        return event

    def read_events(self, event_type: str | None = None) -> list[AnalyticsEvent]:
        return list(self._iter_events(self._events_path, event_type=event_type))

    def read_failures(self, failure_type: str | None = None) -> list[AnalyticsEvent]:
        events = self._iter_events(self._failures_path, event_type="failure")
        if failure_type is None:
            return list(events)
        return [e for e in events if e.payload.get("failure_type") == failure_type]

    def _iter_events(self, path: Path, event_type: str | None) -> Iterable[AnalyticsEvent]:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = AnalyticsEvent(
                event_type=record.get("event_type", "unknown"),
                timestamp=record.get("timestamp", ""),
                payload=record.get("payload", {}),
            )
            if event_type and event.event_type != event_type:
                continue
            yield event

    def clear(self) -> None:
        with self._lock:
            if self._events_path.exists():
                self._events_path.unlink()
            if self._failures_path.exists():
                self._failures_path.unlink()


_collector_singleton: AnalyticsCollector | None = None


def get_collector() -> AnalyticsCollector:
    global _collector_singleton
    if _collector_singleton is None:
        events_path = os.environ.get("ANALYTICS_EVENTS_PATH", str(DEFAULT_EVENTS_PATH))
        failures_path = os.environ.get("ANALYTICS_FAILURES_PATH", str(DEFAULT_FAILURES_PATH))
        _collector_singleton = AnalyticsCollector(events_path=events_path, failures_path=failures_path)
    return _collector_singleton


def reset_collector_singleton() -> None:
    """Test helper to reset singleton state."""
    global _collector_singleton
    _collector_singleton = None
