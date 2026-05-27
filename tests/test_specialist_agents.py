"""Tests for specialist agents."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.specialists import AgentResult, BaseSpecialist
from app.agents.specialists.comparator_agent import ComparatorAgent
from app.agents.specialists.extractor_agent import ExtractorAgent
from app.agents.specialists.qa_agent import QAAgent
from app.agents.specialists.summarizer_agent import SummarizerAgent


class TestBaseSpecialist:
    def test_agent_result_dataclass(self):
        r = AgentResult(success=True, output="done", data={"k": "v"}, agent_id="test")
        assert r.success is True
        assert r.output == "done"
        assert r.data == {"k": "v"}
        assert r.error is None

    def test_can_handle(self):
        agent = ExtractorAgent()
        assert agent.can_handle("upload") is True
        assert agent.can_handle("qa") is False

    def test_describe(self):
        agent = QAAgent()
        desc = agent.describe()
        assert desc["name"] == "qa"
        assert "qa" in desc["capabilities"]


class TestExtractorAgent:
    def test_missing_context_returns_error(self):
        agent = ExtractorAgent()
        result = agent.execute("parse something")
        assert result.success is False
        assert "file_path" in result.error

    def test_file_not_found(self):
        agent = ExtractorAgent()
        result = agent.execute("parse", context={"file_path": "/nonexistent/file.pdf"})
        assert result.success is False
        assert "不存在" in result.error

    @patch("app.services.pdf_parser.load_parsed_result")
    def test_extract_info_success(self, mock_load):
        mock_parsed = MagicMock()
        mock_parsed.title = "Test Paper"
        mock_parsed.abstract = "This is an abstract about testing."
        mock_parsed.sections = [
            MagicMock(heading="Introduction"),
            MagicMock(heading="Method"),
        ]
        mock_load.return_value = mock_parsed

        agent = ExtractorAgent()
        result = agent.execute("extract", context={"paper_id": "paper-1"})
        assert result.success is True
        assert result.data["title"] == "Test Paper"
        assert len(result.data["sections"]) == 2

    @patch("app.services.pdf_parser.load_parsed_result")
    def test_extract_paper_not_found(self, mock_load):
        mock_load.return_value = None
        agent = ExtractorAgent()
        result = agent.execute("extract", context={"paper_id": "missing"})
        assert result.success is False


class TestSummarizerAgent:
    def test_missing_paper_id(self):
        agent = SummarizerAgent()
        result = agent.execute("generate note")
        assert result.success is False
        assert "paper_id" in result.error


class TestQAAgent:
    @patch("app.services.paper_qa.answer_question")
    @patch("app.services.llm_client.LLMClient")
    @patch("app.services.embedding_client.EmbeddingClient")
    @patch("app.services.vector_store.VectorStore")
    def test_answer_question_success(self, mock_vs, mock_ec, mock_llm, mock_aq):
        mock_aq.return_value = {
            "answer": "RAG combines retrieval with generation.",
            "sources": [{"paper_id": "p1", "section": "Method", "chunk_id": "c1"}],
        }

        agent = QAAgent(enable_rerank=False, enable_query_rewrite=False)
        result = agent.execute("What is RAG?", context={"question": "What is RAG?"})
        assert result.success is True
        assert "RAG" in result.output
        assert result.data["source_count"] == 1

    @patch("app.services.paper_qa.answer_question")
    @patch("app.services.llm_client.LLMClient")
    @patch("app.services.embedding_client.EmbeddingClient")
    @patch("app.services.vector_store.VectorStore")
    def test_answer_question_failure(self, mock_vs, mock_ec, mock_llm, mock_aq):
        mock_aq.side_effect = RuntimeError("LLM unavailable")

        agent = QAAgent(enable_rerank=False, enable_query_rewrite=False)
        result = agent.execute("question", context={"question": "test"})
        assert result.success is False
        assert "LLM unavailable" in result.error


class TestComparatorAgent:
    def test_too_few_papers(self):
        agent = ComparatorAgent()
        result = agent.execute("compare", context={"paper_ids": ["p1"]})
        assert result.success is False
        assert "至少" in result.error

    @patch("app.services.paper_compare.compare_papers")
    @patch("app.services.pdf_parser.load_parsed_result")
    @patch("app.services.llm_client.LLMClient")
    def test_compare_success(self, mock_llm, mock_load, mock_compare):
        mock_parsed = MagicMock()
        mock_load.return_value = mock_parsed
        mock_compare.return_value = "comparison result text"

        agent = ComparatorAgent()
        result = agent.execute("compare", context={"paper_ids": ["p1", "p2"]})
        assert result.success is True
        assert result.data["paper_count"] == 2
