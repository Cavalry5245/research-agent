"""Research workflow — end-to-end paper analysis pipeline.

parse → index → note → (optional qa)
"""

import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.tools.paper_tools import (
    GenerateNoteTool,
    IndexPaperTool,
    QATool,
    UploadPaperTool,
)

logger = logging.getLogger(__name__)


class ResearchWorkflowState(TypedDict):
    paper_id: str
    file_path: str
    question: str
    top_k: int
    # Progress tracking
    parsed: bool
    indexed: bool
    note_generated: bool
    # Results
    title: str
    sections_count: int
    chars: int
    chunks_indexed: int
    note_path: str
    note_length: int
    answer: str
    sources_count: int
    # Error
    error: str


# ── Nodes ────────────────────────────────────────────────────────────────────


def parse_node(state: ResearchWorkflowState) -> dict:
    tool = UploadPaperTool()
    result = tool.execute(file_path=state["file_path"])
    if not result.success:
        return {"error": result.error or "parse failed"}
    return {
        "paper_id": result.data["paper_id"],
        "title": result.data.get("title", ""),
        "sections_count": result.data.get("sections", 0),
        "chars": result.data.get("chars", 0),
        "parsed": True,
    }


def index_node(state: ResearchWorkflowState) -> dict:
    if state.get("error"):
        return {}
    tool = IndexPaperTool()
    result = tool.execute(paper_id=state["paper_id"])
    if not result.success:
        return {"error": result.error or "index failed"}
    return {
        "indexed": True,
        "chunks_indexed": result.data.get("chunks_indexed", 0),
    }


def note_node(state: ResearchWorkflowState) -> dict:
    if state.get("error"):
        return {}
    tool = GenerateNoteTool()
    result = tool.execute(paper_id=state["paper_id"])
    if not result.success:
        return {"error": result.error or "note generation failed"}
    return {
        "note_generated": True,
        "note_path": result.data.get("note_path", ""),
        "note_length": result.data.get("content_length", 0),
    }


def qa_node(state: ResearchWorkflowState) -> dict:
    if state.get("error") or not state.get("question"):
        return {}
    tool = QATool()
    result = tool.execute(
        question=state["question"],
        paper_id=state.get("paper_id"),
        top_k=state.get("top_k", 5),
    )
    if not result.success:
        return {"error": result.error or "qa failed"}
    return {
        "answer": result.data.get("answer", ""),
        "sources_count": result.data.get("sources_count", 0),
    }


# ── Routing ──────────────────────────────────────────────────────────────────


def should_continue_qa(state: ResearchWorkflowState) -> str:
    if state.get("error"):
        return END
    if state.get("question"):
        return "qa"
    return END


def should_index(state: ResearchWorkflowState) -> str:
    if state.get("error"):
        return END
    return "index"


def should_note(state: ResearchWorkflowState) -> str:
    if state.get("error"):
        return END
    return "note"


# ── Graph ────────────────────────────────────────────────────────────────────


def build_research_workflow() -> StateGraph:
    workflow = StateGraph(ResearchWorkflowState)

    workflow.add_node("parse", parse_node)
    workflow.add_node("index", index_node)
    workflow.add_node("note", note_node)
    workflow.add_node("qa", qa_node)

    workflow.set_entry_point("parse")
    workflow.add_conditional_edges("parse", should_index, {"index": "index", END: END})
    workflow.add_conditional_edges("index", should_note, {"note": "note", END: END})
    workflow.add_conditional_edges("note", should_continue_qa, {"qa": "qa", END: END})
    workflow.add_edge("qa", END)

    return workflow.compile()


# ── Mermaid ──────────────────────────────────────────────────────────────────


def export_mermaid() -> str:
    graph = build_research_workflow()
    return graph.get_graph().draw_mermaid()