"""Tests for DecisionLogger — routing decision recording and statistics."""

import json

import pytest

from app.agents.decision_logger import DecisionLogger, RoutingDecision
from app.services.memory_store import MemoryStore


@pytest.fixture
def store(tmp_path):
    return MemoryStore(db_path=tmp_path / "test_decisions.db")


@pytest.fixture
def logger(store):
    return DecisionLogger(store, conversation_id="conv-decision-001")


class TestRoutingDecision:
    def test_defaults(self):
        d = RoutingDecision(user_input="test", classified_type="qa", routed_to="qa")
        assert d.confidence_scores == {}
        assert d.rationale == ""


class TestDecisionLogger:
    def test_log_routing_persists(self, logger, store):
        trace_id = logger.log_routing(
            user_input="这篇论文的方法是什么？",
            classified_type="qa",
            routed_to="qa",
            confidence_scores={"qa": 3, "extract": 1},
            rationale="Multiple question keywords matched",
        )
        assert trace_id

        traces = store.get_traces(conversation_id="conv-decision-001")
        assert len(traces) == 1
        output = json.loads(traces[0]["output_data"])
        assert output["classified_type"] == "qa"
        assert output["routed_to"] == "qa"
        assert output["confidence_scores"] == {"qa": 3, "extract": 1}

    def test_log_routing_appends_to_decisions(self, logger):
        logger.log_routing("q1", "qa", "qa")
        logger.log_routing("compare papers", "compare", "comparator")
        assert len(logger.decisions) == 2
        assert logger.decisions[0].classified_type == "qa"
        assert logger.decisions[1].routed_to == "comparator"

    def test_log_delegation_result(self, logger, store):
        trace_id = logger.log_delegation_result(
            agent_id="qa_agent",
            success=True,
            duration_ms=450.5,
            output_summary="Answer generated successfully",
        )
        assert trace_id
        traces = store.get_traces(agent_id="qa_agent")
        assert len(traces) == 1
        assert traces[0]["action"] == "delegation_result"
        assert traces[0]["duration_ms"] == pytest.approx(450.5)

    def test_log_delegation_result_with_error(self, logger, store):
        logger.log_delegation_result(
            agent_id="extractor",
            success=False,
            duration_ms=100,
            error="Paper not found",
        )
        traces = store.get_traces(agent_id="extractor")
        output = json.loads(traces[0]["output_data"])
        assert output["success"] is False
        assert output["error"] == "Paper not found"

    def test_get_routing_history(self, logger):
        logger.log_routing("q1", "qa", "qa")
        logger.log_routing("compare", "compare", "comparator")
        logger.log_delegation_result("qa", True, 100)

        history = logger.get_routing_history()
        assert len(history) == 2
        for h in history:
            meta = json.loads(h["metadata"])
            assert meta["type"] == "routing_decision"

    def test_get_routing_stats(self, logger):
        logger.log_routing("q1", "qa", "qa")
        logger.log_routing("q2", "qa", "qa")
        logger.log_routing("compare", "compare", "comparator")

        stats = logger.get_routing_stats()
        assert stats["total_decisions"] == 3
        assert stats["by_type"] == {"qa": 2, "compare": 1}
        assert stats["by_agent"] == {"qa": 2, "comparator": 1}

    def test_get_routing_stats_empty(self, logger):
        stats = logger.get_routing_stats()
        assert stats == {"total_decisions": 0, "by_type": {}, "by_agent": {}}

    def test_no_conversation_id(self, store):
        logger = DecisionLogger(store, conversation_id=None)
        logger.log_routing("test", "qa", "qa")
        traces = store.get_traces(agent_id="supervisor")
        assert len(traces) == 1
        assert traces[0]["conversation_id"] is None
