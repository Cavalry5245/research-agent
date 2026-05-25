"""Tests for AgentTracer — span recording, persistence, and statistics."""

import json
import time

import pytest

from app.agents.tracing import AgentTracer, TraceSpan
from app.services.memory_store import MemoryStore


@pytest.fixture
def store(tmp_path):
    return MemoryStore(db_path=tmp_path / "test_trace.db")


@pytest.fixture
def tracer(store):
    return AgentTracer(store, conversation_id="conv-test-001")


class TestTraceSpan:
    def test_span_defaults(self):
        s = TraceSpan(agent_id="qa", action="tool_call")
        assert s.input_data == {}
        assert s.output_data == {}
        assert s.children == []
        assert s.duration_ms == 0.0


class TestAgentTracer:
    def test_span_context_manager_records_duration(self, tracer):
        with tracer.span("qa_agent", "tool_call", input_data={"tool": "search"}) as s:
            time.sleep(0.01)
            s.output_data = {"results": 3}

        assert s.duration_ms >= 10
        assert s.output_data == {"results": 3}
        assert len(tracer.spans) == 1

    def test_span_persists_to_store(self, tracer, store):
        with tracer.span("extractor", "delegation", input_data={"paper_id": "p1"}) as s:
            s.output_data = {"status": "ok"}

        traces = store.get_traces(conversation_id="conv-test-001")
        assert len(traces) == 1
        t = traces[0]
        assert t["agent_id"] == "extractor"
        assert t["action"] == "delegation"
        assert json.loads(t["input_data"]) == {"paper_id": "p1"}
        assert json.loads(t["output_data"]) == {"status": "ok"}
        assert t["duration_ms"] >= 0

    def test_nested_spans_track_children(self, tracer):
        with tracer.span("supervisor", "route") as parent:
            with tracer.span("qa_agent", "tool_call") as child:
                child.output_data = {"answer": "yes"}
            parent.output_data = {"routed_to": "qa"}

        assert len(parent.children) == 1
        assert parent.children[0] is child
        assert len(tracer.spans) == 2

    def test_nested_span_metadata_includes_children_count(self, tracer, store):
        with tracer.span("supervisor", "execute") as parent:
            with tracer.span("tool_a", "tool_call"):
                pass
            with tracer.span("tool_b", "tool_call"):
                pass

        traces = store.get_traces(agent_id="supervisor")
        assert len(traces) == 1
        meta = json.loads(traces[0]["metadata"])
        assert meta["children_count"] == 2

    def test_record_direct(self, tracer, store):
        trace_id = tracer.record(
            agent_id="summarizer",
            action="llm_call",
            input_data={"prompt_tokens": 500},
            output_data={"completion_tokens": 200},
            duration_ms=1234.5,
        )
        assert trace_id
        traces = store.get_traces(agent_id="summarizer")
        assert len(traces) == 1
        assert traces[0]["duration_ms"] == pytest.approx(1234.5)

    def test_conversation_id_setter(self, store):
        tracer = AgentTracer(store)
        assert tracer.conversation_id is None
        tracer.conversation_id = "new-conv"
        tracer.record("agent", "action")
        traces = store.get_traces(conversation_id="new-conv")
        assert len(traces) == 1

    def test_get_execution_timeline(self, tracer):
        tracer.record("a1", "step1", duration_ms=100)
        time.sleep(0.001)
        tracer.record("a2", "step2", duration_ms=200)

        timeline = tracer.get_execution_timeline()
        assert len(timeline) == 2
        assert timeline[0]["agent_id"] == "a1"
        assert timeline[1]["agent_id"] == "a2"
        assert timeline[0]["started_at"] <= timeline[1]["started_at"]

    def test_get_tool_call_stats(self, tracer):
        tracer.record("search", "tool_call", input_data={"tool": "search"}, duration_ms=50)
        tracer.record("search", "tool_call", input_data={"tool": "search"}, duration_ms=70)
        tracer.record("index", "tool_call", input_data={"tool": "index"}, duration_ms=200)
        tracer.record("supervisor", "route", duration_ms=10)

        stats = tracer.get_tool_call_stats()
        assert stats["total_calls"] == 3
        assert stats["total_duration_ms"] == pytest.approx(320)
        assert stats["tools"]["search"]["count"] == 2
        assert stats["tools"]["search"]["avg_ms"] == pytest.approx(60)
        assert stats["tools"]["index"]["count"] == 1

    def test_get_tool_call_stats_empty(self, tracer):
        stats = tracer.get_tool_call_stats()
        assert stats == {"total_calls": 0, "total_duration_ms": 0, "tools": {}}

    def test_span_exception_still_records(self, tracer, store):
        with pytest.raises(ValueError):
            with tracer.span("failing_agent", "tool_call") as s:
                s.output_data = {"partial": True}
                raise ValueError("something broke")

        assert len(tracer.spans) == 1
        assert tracer.spans[0].duration_ms > 0
        traces = store.get_traces(agent_id="failing_agent")
        assert len(traces) == 1
