"""End-to-end integration tests for multi-agent collaboration scenarios.

Tests the full pipeline: supervisor routing → specialist execution → memory persistence.
LLM calls are mocked to allow CI execution without API keys.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.paper_research_agent import PaperResearchAgent
from app.agents.scenarios import (
    run_interactive_session,
    run_multi_paper_comparison,
    run_paper_analysis,
)
from app.agents.supervisor import SupervisorAgent, classify_intent
from app.agents.tracing import AgentTracer
from app.agents.decision_logger import DecisionLogger
from app.services.memory_store import MemoryStore


@pytest.fixture
def memory_store(tmp_path):
    return MemoryStore(db_path=tmp_path / "e2e_test.db")


# ── Scenario 1: Supervisor routing + specialist execution ────────────────────


class TestSupervisorE2E:
    """Full supervisor pipeline: route → execute → synthesize."""

    @patch("app.services.paper_qa.answer_question")
    @patch("app.services.vector_store.VectorStore")
    @patch("app.services.embedding_client.EmbeddingClient")
    def test_qa_routing_full_pipeline(self, mock_emb_cls, mock_vs_cls, mock_answer):
        mock_answer.return_value = {
            "answer": "这是一个关于深度学习的回答。",
            "sources": [{"chunk_id": "c1", "content": "Test", "paper_id": "p1",
                         "title": "Paper", "section": "Method", "score": 0.9}],
        }

        supervisor = SupervisorAgent()
        result = supervisor.run("这篇论文的方法是什么？", context={"paper_id": "p1"})

        assert result["task_type"] == "qa"
        assert result["answer"]
        assert result["error"] is None

    @patch("app.services.llm_client.LLMClient.generate_text")
    def test_compare_routing(self, mock_llm):
        mock_llm.return_value = "## 对比结果\n论文A和B的主要区别在于..."

        supervisor = SupervisorAgent()
        result = supervisor.run("对比这两篇论文的方法", context={"paper_ids": ["p1", "p2"]})

        assert result["task_type"] == "compare"

    def test_intent_classification_coverage(self):
        test_cases = [
            ("上传这篇论文", "upload"),
            ("生成笔记", "note"),
            ("这篇论文的核心贡献是什么？", "qa"),
            ("对比这两篇论文", "compare"),
            ("搜索相关内容", "search"),
            ("导出 markdown", "export"),
        ]
        for text, expected_type in test_cases:
            result = classify_intent(text)
            assert result == expected_type, f"'{text}' classified as '{result}', expected '{expected_type}'"


# ── Scenario 2: Memory persistence across agent execution ────────────────────


class TestMemoryIntegrationE2E:
    """Agent execution persists conversation history and traces."""

    @patch("app.agents.paper_research_agent.create_agent")
    def test_execute_persists_conversation(self, mock_create_agent, memory_store):
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "这是回答"
        mock_graph.invoke.return_value = {"messages": [mock_msg]}
        mock_create_agent.return_value = mock_graph

        agent = PaperResearchAgent(memory_store=memory_store)
        result = agent.execute("测试问题")

        assert result["conversation_id"]
        assert result["answer"] == "这是回答"

        conv = memory_store.get_conversation(result["conversation_id"])
        assert conv is not None
        messages = memory_store.get_messages(result["conversation_id"])
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    @patch("app.agents.paper_research_agent.create_agent")
    def test_multi_turn_conversation(self, mock_create_agent, memory_store):
        mock_graph = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "回答1"
        mock_graph.invoke.return_value = {"messages": [mock_msg]}
        mock_create_agent.return_value = mock_graph

        agent = PaperResearchAgent(memory_store=memory_store)
        r1 = agent.execute("问题1")
        conv_id = r1["conversation_id"]

        mock_msg.content = "回答2"
        r2 = agent.execute("问题2", conversation_id=conv_id)

        assert r2["conversation_id"] == conv_id
        messages = memory_store.get_messages(conv_id)
        assert len(messages) == 4

    def test_tracer_records_to_store(self, memory_store):
        tracer = AgentTracer(memory_store, conversation_id="e2e-conv")

        with tracer.span("supervisor", "route", input_data={"input": "test"}) as s:
            s.output_data = {"type": "qa"}

        with tracer.span("qa_agent", "tool_call", input_data={"tool": "search"}) as s:
            s.output_data = {"results": 3}

        traces = memory_store.get_traces(conversation_id="e2e-conv")
        assert len(traces) == 2

        timeline = tracer.get_execution_timeline()
        assert len(timeline) == 2
        assert timeline[0]["agent_id"] == "supervisor"
        assert timeline[1]["agent_id"] == "qa_agent"

    def test_decision_logger_records_routing(self, memory_store):
        logger = DecisionLogger(memory_store, conversation_id="e2e-conv")

        logger.log_routing(
            user_input="这篇论文的方法是什么",
            classified_type="qa",
            routed_to="qa",
            confidence_scores={"qa": 3, "extract": 1},
        )
        logger.log_delegation_result("qa_agent", success=True, duration_ms=500)

        history = logger.get_routing_history()
        assert len(history) == 1

        stats = logger.get_routing_stats()
        assert stats["total_decisions"] == 1


# ── Scenario 3: Multi-agent scenario graphs ──────────────────────────────────


class TestScenarioGraphsE2E:
    """LangGraph scenario pipelines execute correctly."""

    @patch("app.agents.scenarios.ExtractorAgent")
    @patch("app.agents.scenarios.SummarizerAgent")
    @patch("app.agents.scenarios.QAAgent")
    def test_paper_analysis_scenario(self, mock_qa_cls, mock_sum_cls, mock_ext_cls):
        from app.agents.specialists import AgentResult

        mock_ext = MagicMock()
        mock_ext.execute.return_value = AgentResult(success=True, output="Extracted info")
        mock_ext_cls.return_value = mock_ext

        mock_sum = MagicMock()
        mock_sum.execute.return_value = AgentResult(success=True, output="Summary note")
        mock_sum_cls.return_value = mock_sum

        mock_qa = MagicMock()
        mock_qa.execute.return_value = AgentResult(success=True, output="Answer to question")
        mock_qa_cls.return_value = mock_qa

        result = run_paper_analysis("paper_001", questions=["核心贡献是什么？"])

        assert result["paper_id"] == "paper_001"
        assert result["extract"] is not None
        assert result["summary"] is not None
        assert result["qa"] is not None
        assert len(result["qa"]) == 1
        assert result["qa"][0]["success"] is True

    @patch("app.agents.scenarios.ExtractorAgent")
    @patch("app.agents.scenarios.ComparatorAgent")
    def test_multi_paper_comparison_scenario(self, mock_comp_cls, mock_ext_cls):
        from app.agents.specialists import AgentResult

        mock_ext = MagicMock()
        mock_ext.execute.return_value = AgentResult(success=True, output="Extracted")
        mock_ext_cls.return_value = mock_ext

        mock_comp = MagicMock()
        mock_comp.execute.return_value = AgentResult(success=True, output="Comparison done")
        mock_comp_cls.return_value = mock_comp

        result = run_multi_paper_comparison(["p1", "p2", "p3"])

        assert result["paper_ids"] == ["p1", "p2", "p3"]
        assert result["extractions"] is not None
        assert result["comparison"] is not None

    @patch("app.agents.supervisor.SupervisorAgent")
    def test_interactive_session_scenario(self, mock_sup_cls):
        mock_sup = MagicMock()
        mock_sup.run.side_effect = [
            {"task_type": "qa", "answer": "回答1", "error": None},
            {"task_type": "note", "answer": "笔记已生成", "error": None},
        ]
        mock_sup_cls.return_value = mock_sup

        messages = [
            {"content": "这篇论文讲了什么？"},
            {"content": "帮我生成笔记"},
        ]
        result = run_interactive_session(messages)

        assert result["turns"] == 2
        assert result["responses"][0]["task_type"] == "qa"
        assert result["responses"][1]["task_type"] == "note"


# ── Scenario 4: Observability wired into real execution ──────────────────────


class TestObservabilityWiring:
    """Verify that execute_supervisor writes routing + delegation traces to MemoryStore."""

    @patch("app.agents.paper_research_agent.create_agent")
    @patch("app.services.paper_qa.answer_question")
    @patch("app.services.vector_store.VectorStore")
    @patch("app.services.embedding_client.EmbeddingClient")
    def test_execute_supervisor_writes_routing_decision_trace(
        self, mock_emb, mock_vs, mock_answer, mock_create_agent, memory_store
    ):
        mock_graph = MagicMock()
        mock_create_agent.return_value = mock_graph
        mock_answer.return_value = {"answer": "回答", "sources": []}

        agent = PaperResearchAgent(memory_store=memory_store)
        result = agent.execute_supervisor("这篇论文的方法是什么？")

        conv_id = result["conversation_id"]
        assert conv_id

        traces = memory_store.get_traces(conversation_id=conv_id)
        routing_traces = [t for t in traces if t["action"] == "routing_decision"]
        assert len(routing_traces) >= 1

        import json
        output = json.loads(routing_traces[0]["output_data"])
        assert output["classified_type"] == "qa"
        assert output["routed_to"] == "qa"
        assert "confidence_scores" in output

    @patch("app.agents.paper_research_agent.create_agent")
    @patch("app.services.paper_qa.answer_question")
    @patch("app.services.vector_store.VectorStore")
    @patch("app.services.embedding_client.EmbeddingClient")
    def test_execute_supervisor_writes_delegation_result_trace(
        self, mock_emb, mock_vs, mock_answer, mock_create_agent, memory_store
    ):
        mock_graph = MagicMock()
        mock_create_agent.return_value = mock_graph
        mock_answer.return_value = {"answer": "深度学习方法", "sources": []}

        agent = PaperResearchAgent(memory_store=memory_store)
        result = agent.execute_supervisor("这篇论文用了什么方法？")

        conv_id = result["conversation_id"]
        traces = memory_store.get_traces(conversation_id=conv_id)
        delegation_traces = [t for t in traces if t["action"] == "delegation_result"]
        assert len(delegation_traces) >= 1

        import json
        output = json.loads(delegation_traces[0]["output_data"])
        assert "success" in output
        assert delegation_traces[0]["duration_ms"] is not None

    @patch("app.agents.paper_research_agent.create_agent")
    @patch("app.services.paper_qa.answer_question")
    @patch("app.services.vector_store.VectorStore")
    @patch("app.services.embedding_client.EmbeddingClient")
    def test_execute_supervisor_traces_carry_conversation_id(
        self, mock_emb, mock_vs, mock_answer, mock_create_agent, memory_store
    ):
        mock_graph = MagicMock()
        mock_create_agent.return_value = mock_graph
        mock_answer.return_value = {"answer": "答案", "sources": []}

        agent = PaperResearchAgent(memory_store=memory_store)
        result = agent.execute_supervisor("对比这两篇论文")

        conv_id = result["conversation_id"]
        all_traces = memory_store.get_traces(conversation_id=conv_id)
        assert len(all_traces) >= 2
        for t in all_traces:
            assert t["conversation_id"] == conv_id

    @patch("app.agents.paper_research_agent.create_agent")
    @patch("app.services.paper_qa.answer_question")
    @patch("app.services.vector_store.VectorStore")
    @patch("app.services.embedding_client.EmbeddingClient")
    def test_traces_visible_via_api(
        self, mock_emb, mock_vs, mock_answer, mock_create_agent, memory_store
    ):
        """Verify /api/traces and /api/traces/stats return data from real execution."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.routers.traces import set_trace_store

        mock_graph = MagicMock()
        mock_create_agent.return_value = mock_graph
        mock_answer.return_value = {"answer": "回答", "sources": []}

        set_trace_store(memory_store)
        try:
            agent = PaperResearchAgent(memory_store=memory_store)
            agent.execute_supervisor("搜索相关论文")

            client = TestClient(app)
            resp = client.get("/api/traces")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] >= 2

            resp_stats = client.get("/api/traces/stats")
            assert resp_stats.status_code == 200
            stats = resp_stats.json()
            assert stats["total_traces"] >= 2
            assert "supervisor" in stats["by_agent"]
        finally:
            set_trace_store(None)
