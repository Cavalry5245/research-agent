"""Comparison workflow — multi-paper analysis pipeline.

parse_papers → compare → export
"""

import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.tools.paper_tools import (
    ComparePapersTool,
    ExportMarkdownTool,
    UploadPaperTool,
)

logger = logging.getLogger(__name__)


class ComparisonWorkflowState(TypedDict):
    file_paths: list[str]
    paper_ids: list[str]
    # Progress tracking
    all_parsed: bool
    compared: bool
    exported: bool
    # Results
    titles: list[str]
    output_path: str
    content_length: int
    aspects_count: int
    # Error
    error: str


# ── Nodes ────────────────────────────────────────────────────────────────────


def batch_parse_node(state: ComparisonWorkflowState) -> dict:
    paper_ids: list[str] = []
    titles: list[str] = []
    for fp in state["file_paths"]:
        tool = UploadPaperTool()
        result = tool.execute(file_path=fp)
        if not result.success:
            return {"error": f"Parse failed for {fp}: {result.error}"}
        paper_ids.append(result.data["paper_id"])
        titles.append(result.data.get("title", ""))
    return {
        "paper_ids": paper_ids,
        "titles": titles,
        "all_parsed": True,
    }


def compare_node(state: ComparisonWorkflowState) -> dict:
    if state.get("error"):
        return {}
    tool = ComparePapersTool()
    result = tool.execute(paper_ids=state["paper_ids"])
    if not result.success:
        return {"error": result.error or "comparison failed"}
    return {
        "compared": True,
        "output_path": result.data.get("output_path", ""),
        "content_length": result.data.get("content_length", 0),
        "aspects_count": result.data.get("aspects_count", 0),
    }


def export_node(state: ComparisonWorkflowState) -> dict:
    if state.get("error"):
        return {}
    return {"exported": True}


# ── Routing ──────────────────────────────────────────────────────────────────


def should_compare(state: ComparisonWorkflowState) -> str:
    if state.get("error"):
        return END
    return "compare"


def should_export(state: ComparisonWorkflowState) -> str:
    if state.get("error"):
        return END
    return "export"


# ── Graph ────────────────────────────────────────────────────────────────────


def build_comparison_workflow() -> StateGraph:
    workflow = StateGraph(ComparisonWorkflowState)

    workflow.add_node("parse_papers", batch_parse_node)
    workflow.add_node("compare", compare_node)
    workflow.add_node("export", export_node)

    workflow.set_entry_point("parse_papers")
    workflow.add_conditional_edges(
        "parse_papers", should_compare, {"compare": "compare", END: END}
    )
    workflow.add_conditional_edges(
        "compare", should_export, {"export": "export", END: END}
    )
    workflow.add_edge("export", END)

    return workflow.compile()


def export_comparison_mermaid() -> str:
    graph = build_comparison_workflow()
    return graph.get_graph().draw_mermaid()
