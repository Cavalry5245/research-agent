import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Research workflow tests ──────────────────────────────────────────────────


def test_research_workflow_state():
    from app.agents.workflows.research_workflow import ResearchWorkflowState

    fields = ResearchWorkflowState.__annotations__
    assert "paper_id" in fields
    assert "file_path" in fields
    assert "parsed" in fields
    assert "indexed" in fields
    assert "note_generated" in fields


def test_research_graph_compiles():
    from app.agents.workflows.research_workflow import build_research_workflow

    graph = build_research_workflow()
    assert graph is not None


def test_research_mermaid_export():
    from app.agents.workflows.research_workflow import export_mermaid

    mermaid = export_mermaid()
    assert (
        "graph" in mermaid.lower()
        or "---" in mermaid
        or "flowchart" in mermaid.lower()
        or len(mermaid) > 0
    )


def test_parse_node():
    from app.agents.workflows.research_workflow import parse_node

    with patch("app.agents.workflows.research_workflow.UploadPaperTool") as MockTool:
        mock_instance = MockTool.return_value
        mock_instance.execute.return_value = MagicMock(
            success=True,
            data={
                "paper_id": "paper_A",
                "title": "Test Title",
                "sections": 5,
                "chars": 1000,
            },
        )

        state = {
            "paper_id": "",
            "file_path": "/tmp/test.pdf",
            "question": "",
            "top_k": 5,
            "parsed": False,
            "indexed": False,
            "note_generated": False,
            "title": "",
            "sections_count": 0,
            "chars": 0,
            "chunks_indexed": 0,
            "note_path": "",
            "note_length": 0,
            "answer": "",
            "sources_count": 0,
            "error": "",
        }
        result = parse_node(state)
        assert result["parsed"] is True
        assert result["paper_id"] == "paper_A"
        assert result["title"] == "Test Title"


def test_parse_node_failure():
    from app.agents.workflows.research_workflow import parse_node

    with patch("app.agents.workflows.research_workflow.UploadPaperTool") as MockTool:
        mock_instance = MockTool.return_value
        mock_instance.execute.return_value = MagicMock(
            success=False, error="File not found"
        )

        state = {
            "paper_id": "",
            "file_path": "/tmp/missing.pdf",
            "question": "",
            "top_k": 5,
            "parsed": False,
            "indexed": False,
            "note_generated": False,
            "title": "",
            "sections_count": 0,
            "chars": 0,
            "chunks_indexed": 0,
            "note_path": "",
            "note_length": 0,
            "answer": "",
            "sources_count": 0,
            "error": "",
        }
        result = parse_node(state)
        assert "error" in result


def test_index_node():
    from app.agents.workflows.research_workflow import index_node

    with patch("app.agents.workflows.research_workflow.IndexPaperTool") as MockTool:
        mock_instance = MockTool.return_value
        mock_instance.execute.return_value = MagicMock(
            success=True,
            data={"chunks_indexed": 10},
        )

        state = {
            "paper_id": "paper_A",
            "file_path": "",
            "question": "",
            "top_k": 5,
            "parsed": True,
            "indexed": False,
            "note_generated": False,
            "title": "",
            "sections_count": 0,
            "chars": 0,
            "chunks_indexed": 0,
            "note_path": "",
            "note_length": 0,
            "answer": "",
            "sources_count": 0,
            "error": "",
        }
        result = index_node(state)
        assert result["indexed"] is True
        assert result["chunks_indexed"] == 10


def test_index_node_skips_on_error():
    from app.agents.workflows.research_workflow import index_node

    state = {
        "paper_id": "",
        "file_path": "",
        "question": "",
        "top_k": 5,
        "parsed": False,
        "indexed": False,
        "note_generated": False,
        "title": "",
        "sections_count": 0,
        "chars": 0,
        "chunks_indexed": 0,
        "note_path": "",
        "note_length": 0,
        "answer": "",
        "sources_count": 0,
        "error": "previous error",
    }
    result = index_node(state)
    assert result == {}


def test_note_node():
    from app.agents.workflows.research_workflow import note_node

    with patch("app.agents.workflows.research_workflow.GenerateNoteTool") as MockTool:
        mock_instance = MockTool.return_value
        mock_instance.execute.return_value = MagicMock(
            success=True,
            data={"note_path": "/tmp/note.md", "content_length": 500},
        )

        state = {
            "paper_id": "paper_A",
            "file_path": "",
            "question": "",
            "top_k": 5,
            "parsed": True,
            "indexed": True,
            "note_generated": False,
            "title": "",
            "sections_count": 0,
            "chars": 0,
            "chunks_indexed": 0,
            "note_path": "",
            "note_length": 0,
            "answer": "",
            "sources_count": 0,
            "error": "",
        }
        result = note_node(state)
        assert result["note_generated"] is True
        assert result["note_path"] == "/tmp/note.md"


def test_qa_node():
    from app.agents.workflows.research_workflow import qa_node

    with patch("app.agents.workflows.research_workflow.QATool") as MockTool:
        mock_instance = MockTool.return_value
        mock_instance.execute.return_value = MagicMock(
            success=True,
            data={"answer": "核心创新是...", "sources_count": 3},
        )

        state = {
            "paper_id": "paper_A",
            "file_path": "",
            "question": "核心创新点？",
            "top_k": 5,
            "parsed": True,
            "indexed": True,
            "note_generated": True,
            "title": "",
            "sections_count": 0,
            "chars": 0,
            "chunks_indexed": 0,
            "note_path": "",
            "note_length": 0,
            "answer": "",
            "sources_count": 0,
            "error": "",
        }
        result = qa_node(state)
        assert "answer" in result
        assert result["sources_count"] == 3


def test_qa_node_skips_without_question():
    from app.agents.workflows.research_workflow import qa_node

    state = {
        "paper_id": "paper_A",
        "file_path": "",
        "question": "",
        "top_k": 5,
        "parsed": True,
        "indexed": True,
        "note_generated": True,
        "title": "",
        "sections_count": 0,
        "chars": 0,
        "chunks_indexed": 0,
        "note_path": "",
        "note_length": 0,
        "answer": "",
        "sources_count": 0,
        "error": "",
    }
    result = qa_node(state)
    assert result == {}


# ── Conditional routing tests ────────────────────────────────────────────────


def test_should_continue_qa_with_question():
    from app.agents.workflows.research_workflow import should_continue_qa

    state = {
        "paper_id": "",
        "file_path": "",
        "question": "核心创新？",
        "top_k": 5,
        "parsed": True,
        "indexed": True,
        "note_generated": True,
        "title": "",
        "sections_count": 0,
        "chars": 0,
        "chunks_indexed": 0,
        "note_path": "",
        "note_length": 0,
        "answer": "",
        "sources_count": 0,
        "error": "",
    }
    result = should_continue_qa(state)
    assert result == "qa"


def test_should_continue_qa_without_question():
    from langgraph.graph import END

    from app.agents.workflows.research_workflow import should_continue_qa

    state = {
        "paper_id": "",
        "file_path": "",
        "question": "",
        "top_k": 5,
        "parsed": True,
        "indexed": True,
        "note_generated": True,
        "title": "",
        "sections_count": 0,
        "chars": 0,
        "chunks_indexed": 0,
        "note_path": "",
        "note_length": 0,
        "answer": "",
        "sources_count": 0,
        "error": "",
    }
    result = should_continue_qa(state)
    assert result == END


# ── Full workflow execution tests ────────────────────────────────────────────


@patch("app.agents.workflows.research_workflow.UploadPaperTool")
@patch("app.agents.workflows.research_workflow.IndexPaperTool")
@patch("app.agents.workflows.research_workflow.GenerateNoteTool")
def test_research_workflow_full(mock_note, mock_index, mock_upload):
    from app.agents.workflows.research_workflow import build_research_workflow

    mock_upload.return_value.execute.return_value = MagicMock(
        success=True,
        data={"paper_id": "paper_X", "title": "Paper X", "sections": 3, "chars": 5000},
    )
    mock_index.return_value.execute.return_value = MagicMock(
        success=True, data={"chunks_indexed": 8}
    )
    mock_note.return_value.execute.return_value = MagicMock(
        success=True, data={"note_path": "/tmp/note.md", "content_length": 600}
    )

    graph = build_research_workflow()
    result = graph.invoke(
        {
            "paper_id": "",
            "file_path": "/tmp/test.pdf",
            "question": "",
            "top_k": 5,
            "parsed": False,
            "indexed": False,
            "note_generated": False,
            "title": "",
            "sections_count": 0,
            "chars": 0,
            "chunks_indexed": 0,
            "note_path": "",
            "note_length": 0,
            "answer": "",
            "sources_count": 0,
            "error": "",
        }
    )

    assert result["parsed"] is True
    assert result["indexed"] is True
    assert result["note_generated"] is True
    assert result["paper_id"] == "paper_X"


@patch("app.agents.workflows.research_workflow.UploadPaperTool")
@patch("app.agents.workflows.research_workflow.IndexPaperTool")
@patch("app.agents.workflows.research_workflow.GenerateNoteTool")
@patch("app.agents.workflows.research_workflow.QATool")
def test_research_workflow_with_qa(mock_qa, mock_note, mock_index, mock_upload):
    from app.agents.workflows.research_workflow import build_research_workflow

    mock_upload.return_value.execute.return_value = MagicMock(
        success=True,
        data={"paper_id": "paper_Y", "title": "Paper Y", "sections": 4, "chars": 8000},
    )
    mock_index.return_value.execute.return_value = MagicMock(
        success=True, data={"chunks_indexed": 12}
    )
    mock_note.return_value.execute.return_value = MagicMock(
        success=True, data={"note_path": "/tmp/note2.md", "content_length": 700}
    )
    mock_qa.return_value.execute.return_value = MagicMock(
        success=True, data={"answer": "这篇论文提出了VLM方法", "sources_count": 5}
    )

    graph = build_research_workflow()
    result = graph.invoke(
        {
            "paper_id": "",
            "file_path": "/tmp/test.pdf",
            "question": "核心创新是什么？",
            "top_k": 3,
            "parsed": False,
            "indexed": False,
            "note_generated": False,
            "title": "",
            "sections_count": 0,
            "chars": 0,
            "chunks_indexed": 0,
            "note_path": "",
            "note_length": 0,
            "answer": "",
            "sources_count": 0,
            "error": "",
        }
    )

    assert result["parsed"] is True
    assert result["indexed"] is True
    assert result["note_generated"] is True
    assert "VLM" in result["answer"]
    assert result["sources_count"] == 5


# ── Comparison workflow tests ────────────────────────────────────────────────


def test_comparison_workflow_state():
    from app.agents.workflows.comparison_workflow import ComparisonWorkflowState

    fields = ComparisonWorkflowState.__annotations__
    assert "file_paths" in fields
    assert "paper_ids" in fields
    assert "all_parsed" in fields
    assert "compared" in fields
    assert "exported" in fields


def test_comparison_graph_compiles():
    from app.agents.workflows.comparison_workflow import build_comparison_workflow

    graph = build_comparison_workflow()
    assert graph is not None


def test_comparison_mermaid_export():
    from app.agents.workflows.comparison_workflow import export_comparison_mermaid

    mermaid = export_comparison_mermaid()
    assert len(mermaid) > 0


@patch("app.agents.workflows.comparison_workflow.UploadPaperTool")
@patch("app.agents.workflows.comparison_workflow.ComparePapersTool")
def test_comparison_workflow_full(mock_compare, mock_upload):
    from app.agents.workflows.comparison_workflow import build_comparison_workflow

    # Return different paper_ids for each call
    mock_upload.return_value.execute.side_effect = [
        MagicMock(success=True, data={"paper_id": "paper_1", "title": "Paper 1"}),
        MagicMock(success=True, data={"paper_id": "paper_2", "title": "Paper 2"}),
    ]
    mock_compare.return_value.execute.return_value = MagicMock(
        success=True,
        data={
            "output_path": "/tmp/compare.md",
            "content_length": 3000,
            "aspects_count": 5,
        },
    )

    graph = build_comparison_workflow()
    result = graph.invoke(
        {
            "file_paths": ["/tmp/p1.pdf", "/tmp/p2.pdf"],
            "paper_ids": [],
            "all_parsed": False,
            "compared": False,
            "exported": False,
            "titles": [],
            "output_path": "",
            "content_length": 0,
            "aspects_count": 0,
            "error": "",
        }
    )

    assert result["all_parsed"] is True
    assert result["compared"] is True
    assert result["exported"] is True
    assert len(result["paper_ids"]) == 2
    assert result["aspects_count"] == 5


# ── Persistence test ─────────────────────────────────────────────────────────


def test_workflow_state_serializable():
    """Verify workflow state is serializable (plain dict, no complex objects)."""
    from app.agents.workflows.research_workflow import ResearchWorkflowState

    state: ResearchWorkflowState = {
        "paper_id": "paper_A",
        "file_path": "/tmp/test.pdf",
        "question": "test?",
        "top_k": 5,
        "parsed": True,
        "indexed": True,
        "note_generated": True,
        "title": "A Title",
        "sections_count": 4,
        "chars": 1000,
        "chunks_indexed": 10,
        "note_path": "/tmp/note.md",
        "note_length": 500,
        "answer": "answer text",
        "sources_count": 3,
        "error": "",
    }

    import json

    serialized = json.dumps(state)
    restored = json.loads(serialized)
    assert restored["paper_id"] == "paper_A"
    assert restored["parsed"] is True
