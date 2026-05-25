"""Tests for multi-agent collaboration scenarios."""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.scenarios import (
    run_interactive_session,
    run_multi_paper_comparison,
    run_paper_analysis,
)
from app.agents.specialists import AgentResult


def _ok(name: str, output: str = "ok") -> AgentResult:
    return AgentResult(success=True, output=output, data={"k": "v"}, agent_id=name)


class TestPaperAnalysisScenario:
    @patch("app.agents.scenarios.QAAgent")
    @patch("app.agents.scenarios.SummarizerAgent")
    @patch("app.agents.scenarios.ExtractorAgent")
    def test_full_analysis_pipeline(self, mock_ext_cls, mock_sum_cls, mock_qa_cls):
        mock_ext = MagicMock()
        mock_ext.execute.return_value = _ok("extractor", "extracted")
        mock_ext_cls.return_value = mock_ext

        mock_sum = MagicMock()
        mock_sum.execute.return_value = _ok("summarizer", "summarized")
        mock_sum_cls.return_value = mock_sum

        mock_qa = MagicMock()
        mock_qa.execute.return_value = _ok("qa", "answered")
        mock_qa_cls.return_value = mock_qa

        result = run_paper_analysis("paper-1", questions=["What is the contribution?"])

        assert result["paper_id"] == "paper-1"
        assert result["extract"].success is True
        assert result["summary"].success is True
        assert len(result["qa"]) == 1
        assert result["qa"][0]["success"] is True


class TestMultiPaperComparisonScenario:
    @patch("app.agents.scenarios.ComparatorAgent")
    @patch("app.agents.scenarios.ExtractorAgent")
    def test_comparison_pipeline(self, mock_ext_cls, mock_comp_cls):
        mock_ext = MagicMock()
        mock_ext.execute.return_value = _ok("extractor")
        mock_ext_cls.return_value = mock_ext

        mock_comp = MagicMock()
        mock_comp.execute.return_value = _ok("comparator", "compared")
        mock_comp_cls.return_value = mock_comp

        result = run_multi_paper_comparison(["p1", "p2", "p3"])

        assert len(result["extractions"]) == 3
        assert result["comparison"].success is True
        assert mock_ext.execute.call_count == 3


class TestInteractiveSessionScenario:
    @patch("app.agents.supervisor.ComparatorAgent")
    @patch("app.agents.supervisor.QAAgent")
    @patch("app.agents.supervisor.SummarizerAgent")
    @patch("app.agents.supervisor.ExtractorAgent")
    def test_multi_turn_session(self, mock_ext, mock_sum, mock_qa, mock_comp):
        mock_qa_inst = MagicMock()
        mock_qa_inst.execute.return_value = _ok("qa", "RAG answer")
        mock_qa.return_value = mock_qa_inst

        mock_sum_inst = MagicMock()
        mock_sum_inst.execute.return_value = _ok("summarizer", "note generated")
        mock_sum.return_value = mock_sum_inst

        mock_ext.return_value = MagicMock()
        mock_comp.return_value = MagicMock()

        messages = [
            {"content": "What is RAG?"},
            {"content": "生成笔记"},
        ]

        result = run_interactive_session(messages)
        assert result["turns"] == 2
        assert result["responses"][0]["task_type"] == "qa"
        assert result["responses"][1]["task_type"] == "note"
