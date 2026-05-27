"""DecisionLogger — records supervisor routing decisions with rationale."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.memory_store import MemoryStore


@dataclass
class RoutingDecision:
    user_input: str
    classified_type: str
    routed_to: str
    confidence_scores: dict[str, int] = field(default_factory=dict)
    rationale: str = ""
    timestamp: float = 0.0


class DecisionLogger:
    """Logs supervisor routing decisions to the memory store for observability.

    Each decision captures: what the user said, how it was classified,
    which specialist was chosen, and the keyword match scores that drove the choice.
    """

    def __init__(self, store: MemoryStore, conversation_id: str | None = None):
        self._store = store
        self._conversation_id = conversation_id
        self._decisions: list[RoutingDecision] = []

    @property
    def decisions(self) -> list[RoutingDecision]:
        return list(self._decisions)

    def log_routing(
        self,
        user_input: str,
        classified_type: str,
        routed_to: str,
        confidence_scores: dict[str, int] | None = None,
        rationale: str = "",
    ) -> str:
        """Log a routing decision and persist to the trace store.

        Returns the trace ID.
        """
        decision = RoutingDecision(
            user_input=user_input,
            classified_type=classified_type,
            routed_to=routed_to,
            confidence_scores=confidence_scores or {},
            rationale=rationale,
            timestamp=time.time(),
        )
        self._decisions.append(decision)

        trace_id = self._store.add_trace(
            agent_id="supervisor",
            action="routing_decision",
            input_data=json.dumps({"user_input": user_input}, ensure_ascii=False),
            output_data=json.dumps(
                {
                    "classified_type": classified_type,
                    "routed_to": routed_to,
                    "confidence_scores": confidence_scores or {},
                    "rationale": rationale,
                },
                ensure_ascii=False,
            ),
            duration_ms=0.0,
            conversation_id=self._conversation_id,
            metadata=json.dumps({"type": "routing_decision"}, ensure_ascii=False),
        )
        return trace_id

    def log_delegation_result(
        self,
        agent_id: str,
        success: bool,
        duration_ms: float,
        output_summary: str = "",
        error: str | None = None,
    ) -> str:
        """Log the result of a delegation to a specialist."""
        return self._store.add_trace(
            agent_id=agent_id,
            action="delegation_result",
            input_data="{}",
            output_data=json.dumps(
                {
                    "success": success,
                    "output_summary": output_summary[:500],
                    "error": error,
                },
                ensure_ascii=False,
            ),
            duration_ms=duration_ms,
            conversation_id=self._conversation_id,
            metadata=json.dumps({"type": "delegation_result"}, ensure_ascii=False),
        )

    def get_routing_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent routing decisions from the store."""
        traces = self._store.get_traces(agent_id="supervisor", limit=limit)
        return [
            t
            for t in traces
            if json.loads(t.get("metadata", "{}")).get("type") == "routing_decision"
        ]

    def get_routing_stats(self) -> dict[str, Any]:
        """Aggregate routing statistics from in-memory decisions."""
        if not self._decisions:
            return {"total_decisions": 0, "by_type": {}, "by_agent": {}}

        by_type: dict[str, int] = {}
        by_agent: dict[str, int] = {}
        for d in self._decisions:
            by_type[d.classified_type] = by_type.get(d.classified_type, 0) + 1
            by_agent[d.routed_to] = by_agent.get(d.routed_to, 0) + 1

        return {
            "total_decisions": len(self._decisions),
            "by_type": by_type,
            "by_agent": by_agent,
        }
