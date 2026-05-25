"""Tests for /api/traces endpoints."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.traces import set_trace_store
from app.services.memory_store import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(db_path=tmp_path / "test_traces_api.db")
    set_trace_store(s)
    yield s
    set_trace_store(None)


@pytest.fixture
def client(store):
    return TestClient(app)


class TestListTraces:
    def test_empty(self, client):
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["traces"] == []

    def test_returns_traces(self, client, store):
        store.add_trace(
            agent_id="qa_agent",
            action="tool_call",
            input_data=json.dumps({"tool": "search"}),
            output_data=json.dumps({"results": 5}),
            duration_ms=123.4,
            conversation_id="conv-1",
        )
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        t = data["traces"][0]
        assert t["agent_id"] == "qa_agent"
        assert t["action"] == "tool_call"
        assert t["input_data"] == {"tool": "search"}
        assert t["duration_ms"] == pytest.approx(123.4)

    def test_filter_by_agent_id(self, client, store):
        store.add_trace(agent_id="qa", action="call", duration_ms=10)
        store.add_trace(agent_id="summarizer", action="call", duration_ms=20)

        resp = client.get("/api/traces?agent_id=qa")
        data = resp.json()
        assert data["count"] == 1
        assert data["traces"][0]["agent_id"] == "qa"

    def test_filter_by_conversation_id(self, client, store):
        store.add_trace(agent_id="a", action="x", conversation_id="c1", duration_ms=5)
        store.add_trace(agent_id="a", action="x", conversation_id="c2", duration_ms=5)

        resp = client.get("/api/traces?conversation_id=c1")
        data = resp.json()
        assert data["count"] == 1

    def test_limit_param(self, client, store):
        for i in range(10):
            store.add_trace(agent_id="a", action="x", duration_ms=float(i))

        resp = client.get("/api/traces?limit=3")
        data = resp.json()
        assert data["count"] == 3


class TestTraceStats:
    def test_empty_stats(self, client):
        resp = client.get("/api/traces/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_traces"] == 0
        assert data["avg_duration_ms"] == 0.0

    def test_stats_aggregation(self, client, store):
        store.add_trace(agent_id="qa", action="tool_call", duration_ms=100)
        store.add_trace(agent_id="qa", action="tool_call", duration_ms=200)
        store.add_trace(agent_id="summarizer", action="llm_call", duration_ms=300)

        resp = client.get("/api/traces/stats")
        data = resp.json()
        assert data["total_traces"] == 3
        assert data["by_agent"] == {"qa": 2, "summarizer": 1}
        assert data["by_action"] == {"tool_call": 2, "llm_call": 1}
        assert data["avg_duration_ms"] == pytest.approx(200.0)
