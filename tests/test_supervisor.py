"""Tests for the Supervisor Agent and state routing."""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.state import TASK_TYPE_TO_SPECIALIST, SupervisorState
from app.agents.supervisor import (
    SupervisorAgent,
    classify_intent,
    execute_node,
    route_node,
    synthesize_node,
)


class TestClassifyIntent:
    def test_qa_intent(self):
        assert classify_intent("这篇论文的方法是什么？") == "qa"

    def test_note_intent(self):
        assert classify_intent("生成论文笔记") == "note"

    def test_compare_intent(self):
        assert classify_intent("对比这两篇论文") == "compare"

    def test_upload_intent(self):
        assert classify_intent("上传一篇新论文") == "upload"

    def test_export_intent(self):
        assert classify_intent("导出 markdown 文件") == "export"

    def test_default_to_qa(self):
        assert classify_intent("hello world") == "qa"


class TestRouteNode:
    def test_routes_to_correct_specialist(self):
        state: SupervisorState = {
            "user_input": "生成论文笔记",
            "task_type": "unknown",
            "delegations": [],
            "results": [],
            "final_answer": "",
            "error": None,
            "context": {},
        }
        result = route_node(state)
        assert result["task_type"] == "note"
        assert result["delegations"][0]["agent"] == "summarizer"


class TestExecuteNode:
    @patch("app.agents.supervisor.QAAgent")
    def test_executes_delegation(self, mock_qa_cls):
        mock_agent = MagicMock()
        mock_agent.execute.return_value = MagicMock(
            success=True, output="Answer here", data={"k": "v"}, agent_id="qa", error=None
        )
        mock_qa_cls.return_value = mock_agent

        state: SupervisorState = {
            "user_input": "test",
            "task_type": "qa",
            "delegations": [{"agent": "qa", "task": "What is X?", "context": {}}],
            "results": [],
            "final_answer": "",
            "error": None,
            "context": {},
        }

        with patch("app.agents.supervisor.ExtractorAgent"), \
             patch("app.agents.supervisor.SummarizerAgent"), \
             patch("app.agents.supervisor.ComparatorAgent"):
            result = execute_node(state)

        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is True


class TestSynthesizeNode:
    def test_synthesizes_successful_results(self):
        state: SupervisorState = {
            "user_input": "",
            "task_type": "qa",
            "delegations": [],
            "results": [{"success": True, "output": "The answer is 42.", "data": {}, "agent_id": "qa", "error": None}],
            "final_answer": "",
            "error": None,
            "context": {},
        }
        result = synthesize_node(state)
        assert result["final_answer"] == "The answer is 42."
        assert result["error"] is None

    def test_synthesizes_error_results(self):
        state: SupervisorState = {
            "user_input": "",
            "task_type": "qa",
            "delegations": [],
            "results": [{"success": False, "output": "", "data": {}, "agent_id": "qa", "error": "LLM down"}],
            "final_answer": "",
            "error": None,
            "context": {},
        }
        result = synthesize_node(state)
        assert result["final_answer"] == ""
        assert "LLM down" in result["error"]

    def test_empty_results(self):
        state: SupervisorState = {
            "user_input": "",
            "task_type": "qa",
            "delegations": [],
            "results": [],
            "final_answer": "",
            "error": None,
            "context": {},
        }
        result = synthesize_node(state)
        assert "无法处理" in result["final_answer"]


class TestSupervisorAgent:
    @patch("app.agents.supervisor.QAAgent")
    @patch("app.agents.supervisor.ExtractorAgent")
    @patch("app.agents.supervisor.SummarizerAgent")
    @patch("app.agents.supervisor.ComparatorAgent")
    def test_run_routes_and_executes(self, mock_comp, mock_sum, mock_ext, mock_qa):
        mock_qa_instance = MagicMock()
        mock_qa_instance.execute.return_value = MagicMock(
            success=True, output="RAG answer", data={}, agent_id="qa", error=None
        )
        mock_qa.return_value = mock_qa_instance
        mock_ext.return_value = MagicMock()
        mock_sum.return_value = MagicMock()
        mock_comp.return_value = MagicMock()

        supervisor = SupervisorAgent()
        result = supervisor.run("这篇论文的方法是什么？")

        assert result["task_type"] == "qa"
        assert result["answer"] == "RAG answer"
        assert result["error"] is None
