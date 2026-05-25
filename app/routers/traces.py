"""Agent traces API endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.memory_store import MemoryStore

router = APIRouter(prefix="/api/traces", tags=["traces"])

_store_instance: MemoryStore | None = None


def get_trace_store() -> MemoryStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = MemoryStore()
    return _store_instance


def set_trace_store(store: MemoryStore) -> None:
    global _store_instance
    _store_instance = store


class TraceOut(BaseModel):
    id: str
    conversation_id: str | None
    agent_id: str
    action: str
    input_data: dict
    output_data: dict
    duration_ms: float | None
    created_at: float
    metadata: dict


class TraceListResponse(BaseModel):
    traces: list[TraceOut]
    count: int


class TraceStatsResponse(BaseModel):
    total_traces: int
    by_agent: dict[str, int]
    by_action: dict[str, int]
    avg_duration_ms: float


@router.get("", response_model=TraceListResponse)
def list_traces(
    conversation_id: str | None = Query(None),
    agent_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    store = get_trace_store()
    traces = store.get_traces(
        conversation_id=conversation_id,
        agent_id=agent_id,
        limit=limit,
    )
    items = [
        TraceOut(
            id=t["id"],
            conversation_id=t.get("conversation_id"),
            agent_id=t["agent_id"],
            action=t["action"],
            input_data=json.loads(t.get("input_data", "{}")),
            output_data=json.loads(t.get("output_data", "{}")),
            duration_ms=t.get("duration_ms"),
            created_at=t["created_at"],
            metadata=json.loads(t.get("metadata", "{}")),
        )
        for t in traces
    ]
    return TraceListResponse(traces=items, count=len(items))


@router.get("/stats", response_model=TraceStatsResponse)
def trace_stats():
    store = get_trace_store()
    traces = store.get_traces(limit=1000)

    if not traces:
        return TraceStatsResponse(
            total_traces=0, by_agent={}, by_action={}, avg_duration_ms=0.0
        )

    by_agent: dict[str, int] = {}
    by_action: dict[str, int] = {}
    durations: list[float] = []

    for t in traces:
        by_agent[t["agent_id"]] = by_agent.get(t["agent_id"], 0) + 1
        by_action[t["action"]] = by_action.get(t["action"], 0) + 1
        if t.get("duration_ms") is not None:
            durations.append(t["duration_ms"])

    avg_duration = sum(durations) / len(durations) if durations else 0.0

    return TraceStatsResponse(
        total_traces=len(traces),
        by_agent=by_agent,
        by_action=by_action,
        avg_duration_ms=round(avg_duration, 2),
    )
