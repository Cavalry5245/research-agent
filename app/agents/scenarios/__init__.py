"""Collaboration scenarios — multi-agent pipelines for common research workflows."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.specialists import AgentResult
from app.agents.specialists.comparator_agent import ComparatorAgent
from app.agents.specialists.extractor_agent import ExtractorAgent
from app.agents.specialists.qa_agent import QAAgent
from app.agents.specialists.summarizer_agent import SummarizerAgent

# ── Scenario A: Full Paper Analysis ──────────────────────────────────────────


class PaperAnalysisState(TypedDict, total=False):
    paper_id: str
    questions: list[str]
    extract_result: Any
    summarize_result: Any
    qa_results: list[dict]


def _extract_step(state: PaperAnalysisState) -> dict:
    agent = ExtractorAgent()
    result = agent.execute("extract", context={"paper_id": state.get("paper_id", "")})
    return {"extract_result": result}


def _summarize_step(state: PaperAnalysisState) -> dict:
    agent = SummarizerAgent()
    result = agent.execute(
        "generate note", context={"paper_id": state.get("paper_id", "")}
    )
    return {"summarize_result": result}


def _qa_step(state: PaperAnalysisState) -> dict:
    agent = QAAgent(enable_rerank=False, enable_query_rewrite=False)
    paper_id = state.get("paper_id", "")
    questions = state.get("questions") or ["这篇论文的核心贡献是什么？"]
    answers = []
    for q in questions:
        result = agent.execute(q, context={"question": q, "paper_id": paper_id})
        answers.append(
            {"question": q, "answer": result.output, "success": result.success}
        )
    return {"qa_results": answers}


def build_paper_analysis_graph() -> StateGraph:
    graph = StateGraph(PaperAnalysisState)
    graph.add_node("extract", _extract_step)
    graph.add_node("summarize", _summarize_step)
    graph.add_node("qa", _qa_step)
    graph.set_entry_point("extract")
    graph.add_edge("extract", "summarize")
    graph.add_edge("summarize", "qa")
    graph.add_edge("qa", END)
    return graph


def run_paper_analysis(
    paper_id: str, questions: list[str] | None = None
) -> dict[str, Any]:
    graph = build_paper_analysis_graph().compile()
    state: PaperAnalysisState = {
        "paper_id": paper_id,
        "questions": questions or ["这篇论文的核心贡献是什么？"],
    }
    result = graph.invoke(state)
    return {
        "paper_id": paper_id,
        "extract": result.get("extract_result"),
        "summary": result.get("summarize_result"),
        "qa": result.get("qa_results"),
    }


# ── Scenario B: Multi-Paper Comparison ───────────────────────────────────────


class ComparisonState(TypedDict, total=False):
    paper_ids: list[str]
    extract_results: list[dict]
    compare_result: Any


def _batch_extract_step(state: ComparisonState) -> dict:
    agent = ExtractorAgent()
    paper_ids = state.get("paper_ids", [])
    results = []
    for pid in paper_ids:
        r = agent.execute("extract", context={"paper_id": pid})
        results.append({"paper_id": pid, "result": r})
    return {"extract_results": results}


def _compare_step(state: ComparisonState) -> dict:
    agent = ComparatorAgent()
    paper_ids = state.get("paper_ids", [])
    result = agent.execute("compare", context={"paper_ids": paper_ids})
    return {"compare_result": result}


def build_comparison_graph() -> StateGraph:
    graph = StateGraph(ComparisonState)
    graph.add_node("batch_extract", _batch_extract_step)
    graph.add_node("compare", _compare_step)
    graph.set_entry_point("batch_extract")
    graph.add_edge("batch_extract", "compare")
    graph.add_edge("compare", END)
    return graph


def run_multi_paper_comparison(paper_ids: list[str]) -> dict[str, Any]:
    graph = build_comparison_graph().compile()
    state: ComparisonState = {"paper_ids": paper_ids}
    result = graph.invoke(state)
    return {
        "paper_ids": paper_ids,
        "extractions": result.get("extract_results"),
        "comparison": result.get("compare_result"),
    }


# ── Scenario C: Interactive Research Assistant ────────────────────────────────


def run_interactive_session(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Process a sequence of user messages through the supervisor, simulating multi-turn."""
    from app.agents.supervisor import SupervisorAgent

    supervisor = SupervisorAgent()
    responses: list[dict[str, Any]] = []

    for msg in messages:
        user_input = msg.get("content", "")
        context = msg.get("context", {})
        result = supervisor.run(user_input, context=context)
        responses.append(
            {
                "input": user_input,
                "task_type": result["task_type"],
                "answer": result["answer"],
                "error": result.get("error"),
            }
        )

    return {"turns": len(responses), "responses": responses}
