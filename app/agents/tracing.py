"""Agent execution tracer — records tool calls, delegations, and timing to SQLite."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from app.services.memory_store import MemoryStore


@dataclass
class TraceSpan:
    agent_id: str
    action: str
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[TraceSpan] = field(default_factory=list)


class AgentTracer:
    """Records agent execution spans to the memory store.

    Usage:
        tracer = AgentTracer(memory_store, conversation_id="conv-123")
        with tracer.span("qa_agent", "tool_call", input_data={"tool": "search"}) as s:
            result = do_work()
            s.output_data = {"result": result}
        # span is automatically persisted on exit
    """

    def __init__(self, store: MemoryStore, conversation_id: str | None = None):
        self._store = store
        self._conversation_id = conversation_id
        self._spans: list[TraceSpan] = []
        self._active_span: TraceSpan | None = None

    @property
    def conversation_id(self) -> str | None:
        return self._conversation_id

    @conversation_id.setter
    def conversation_id(self, value: str | None) -> None:
        self._conversation_id = value

    @property
    def spans(self) -> list[TraceSpan]:
        return list(self._spans)

    @contextmanager
    def span(
        self,
        agent_id: str,
        action: str,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[TraceSpan, None, None]:
        """Context manager that times a span and persists it on exit."""
        s = TraceSpan(
            agent_id=agent_id,
            action=action,
            input_data=input_data or {},
            started_at=time.time(),
            metadata=metadata or {},
        )

        parent = self._active_span
        if parent is not None:
            parent.children.append(s)

        self._active_span = s
        try:
            yield s
        finally:
            s.duration_ms = (time.time() - s.started_at) * 1000
            self._active_span = parent
            self._spans.append(s)
            self._persist(s)

    def record(
        self,
        agent_id: str,
        action: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Record a completed span directly (non-context-manager usage)."""
        s = TraceSpan(
            agent_id=agent_id,
            action=action,
            input_data=input_data or {},
            output_data=output_data or {},
            started_at=time.time(),
            duration_ms=duration_ms or 0.0,
            metadata=metadata or {},
        )
        self._spans.append(s)
        return self._persist(s)

    def _persist(self, s: TraceSpan) -> str:
        meta = dict(s.metadata)
        if s.children:
            meta["children_count"] = len(s.children)
        return self._store.add_trace(
            agent_id=s.agent_id,
            action=s.action,
            input_data=json.dumps(s.input_data, ensure_ascii=False),
            output_data=json.dumps(s.output_data, ensure_ascii=False),
            duration_ms=s.duration_ms,
            conversation_id=self._conversation_id,
            metadata=json.dumps(meta, ensure_ascii=False),
        )

    def get_execution_timeline(self) -> list[dict[str, Any]]:
        """Return spans as a flat timeline sorted by start time."""
        return sorted(
            [
                {
                    "agent_id": s.agent_id,
                    "action": s.action,
                    "duration_ms": s.duration_ms,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "started_at": s.started_at,
                    "children_count": len(s.children),
                }
                for s in self._spans
            ],
            key=lambda x: x["started_at"],
        )

    def get_tool_call_stats(self) -> dict[str, Any]:
        """Aggregate statistics for tool_call actions."""
        tool_spans = [s for s in self._spans if s.action == "tool_call"]
        if not tool_spans:
            return {"total_calls": 0, "total_duration_ms": 0, "tools": {}}

        tools: dict[str, list[float]] = {}
        for s in tool_spans:
            tool_name = s.input_data.get("tool", s.agent_id)
            tools.setdefault(tool_name, []).append(s.duration_ms)

        return {
            "total_calls": len(tool_spans),
            "total_duration_ms": sum(s.duration_ms for s in tool_spans),
            "tools": {
                name: {
                    "count": len(durations),
                    "total_ms": sum(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "max_ms": max(durations),
                }
                for name, durations in tools.items()
            },
        }
