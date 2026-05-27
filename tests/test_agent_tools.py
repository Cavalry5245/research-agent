import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.tools.base import BaseTool, ToolParameter, ToolResult
from app.agents.tools.paper_tools import (
    ComparePapersTool,
    ExportMarkdownTool,
    GenerateNoteTool,
    IndexPaperTool,
    QATool,
    UploadPaperTool,
)
from app.agents.tools.registry import ToolRegistry

# ── Mock tool for testing ─────────────────────────────────────────────────────


class MockTool(BaseTool):
    name = "mock_tool"
    description = "A mock tool for testing"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="input", type="string", description="Input text"),
        ]

    def execute(self, **kwargs) -> ToolResult:
        val = kwargs.get("input", "")
        return ToolResult(success=True, data={"output": f"processed: {val}"})


# ── BaseTool ──────────────────────────────────────────────────────────────────


def test_base_tool_abstract():
    class IncompleteTool(BaseTool):
        name = "incomplete"
        description = "missing parameters and execute"

    try:
        IncompleteTool()
        assert False, "Should not instantiate"
    except TypeError:
        pass


def test_base_tool_to_dict():
    tool = MockTool()
    d = tool.to_dict()
    assert d["name"] == "mock_tool"
    assert d["description"] == "A mock tool for testing"
    assert len(d["parameters"]) == 1
    assert d["parameters"][0]["name"] == "input"
    assert d["parameters"][0]["required"] is True


def test_tool_result_success():
    r = ToolResult(success=True, data={"key": "value"})
    assert r.success
    assert r.data["key"] == "value"
    assert r.error is None


def test_tool_result_error():
    r = ToolResult(success=False, error="something went wrong")
    assert not r.success
    assert r.error == "something went wrong"
    assert r.data is None


# ── ToolRegistry ──────────────────────────────────────────────────────────────


def test_registry_register_and_get():
    registry = ToolRegistry()
    tool = MockTool()
    registry.register(tool)
    assert registry.get("mock_tool") is tool


def test_registry_get_unknown():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_registry_list_tools():
    registry = ToolRegistry()
    registry.register(MockTool())
    assert len(registry.list_tools()) == 1


def test_registry_list_tool_definitions():
    registry = ToolRegistry()
    registry.register(MockTool())
    defs = registry.list_tool_definitions()
    assert len(defs) == 1
    assert defs[0]["name"] == "mock_tool"


def test_registry_register_all():
    registry = ToolRegistry()

    class ToolA(MockTool):
        name = "tool_a"

    class ToolB(MockTool):
        name = "tool_b"

    registry.register_all([ToolA(), ToolB()])
    assert len(registry.list_tools()) == 2


def test_registry_empty_name():
    registry = ToolRegistry()

    class NoNameTool(BaseTool):
        name = ""
        description = "no name"

        @property
        def parameters(self):
            return []

        def execute(self, **kwargs):
            return ToolResult(success=True)

    import pytest

    with pytest.raises(ValueError, match="must have a name"):
        registry.register(NoNameTool())


# ── UploadPaperTool ────────────────────────────────────────────────────────────


def test_upload_missing_file():
    tool = UploadPaperTool()
    result = tool.execute(file_path="/nonexistent/test.pdf")
    assert not result.success
    assert "不存在" in result.error


def test_upload_non_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_path = os.path.join(tmpdir, "test.txt")
        with open(txt_path, "w") as f:
            f.write("not a pdf")
        tool = UploadPaperTool()
        result = tool.execute(file_path=txt_path)
        assert not result.success
        assert "只支持 PDF" in result.error


@patch("app.agents.tools.paper_tools.parse_pdf")
@patch("app.agents.tools.paper_tools.save_parse_result")
@patch("app.agents.tools.paper_tools.generate_paper_id")
def test_upload_success(mock_gen_id, mock_save, mock_parse):
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        with open(pdf_path, "w") as f:
            f.write("fake pdf content")

        mock_gen_id.return_value = "paper_2026_001"
        mock_result = MagicMock()
        mock_result.title = "Test Paper"
        mock_result.sections = [MagicMock(), MagicMock()]
        mock_result.full_text = "paper content"
        mock_parse.return_value = mock_result

        tool = UploadPaperTool()
        result = tool.execute(file_path=pdf_path)

        assert result.success
        assert result.data["paper_id"] == "paper_2026_001"
        assert result.data["title"] == "Test Paper"


# ── GenerateNoteTool ──────────────────────────────────────────────────────────


def test_generate_note_missing_paper_id():
    tool = GenerateNoteTool()
    result = tool.execute()
    assert not result.success
    assert "缺少 paper_id" in result.error


@patch("app.agents.tools.paper_tools.generate_note")
@patch("app.agents.tools.paper_tools.save_markdown")
def test_generate_note_success(mock_save, mock_generate):
    mock_generate.return_value = "# Note content"
    mock_save.return_value = "/tmp/note.md"

    tool = GenerateNoteTool()
    result = tool.execute(paper_id="paper_test")

    assert result.success
    assert result.data["paper_id"] == "paper_test"


@patch("app.agents.tools.paper_tools.generate_note")
def test_generate_note_not_found(mock_generate):
    mock_generate.side_effect = FileNotFoundError("not found")

    tool = GenerateNoteTool()
    result = tool.execute(paper_id="paper_404")

    assert not result.success
    assert "解析结果不存在" in result.error


# ── IndexPaperTool ────────────────────────────────────────────────────────────


def test_index_missing_paper_id():
    tool = IndexPaperTool()
    result = tool.execute()
    assert not result.success
    assert "缺少 paper_id" in result.error


@patch("app.agents.tools.paper_tools.load_parsed_result")
@patch("app.agents.tools.paper_tools.chunk_paper")
@patch("app.agents.tools.paper_tools.EmbeddingClient")
@patch("app.agents.tools.paper_tools.VectorStore")
def test_index_success(mock_vs, mock_emb, mock_chunk, mock_load):
    mock_load.return_value = {
        "paper_id": "paper_A",
        "title": "Test",
        "abstract": "",
        "sections": [],
        "full_text": "content",
    }
    mock_chunk.return_value = [MagicMock(content="chunk1"), MagicMock(content="chunk2")]
    mock_emb_instance = MagicMock()
    mock_emb_instance.embed_texts.return_value = [[0.1], [0.2]]
    mock_emb.return_value = mock_emb_instance
    mock_vs_instance = MagicMock()
    mock_vs_instance.backend_name.return_value = "chroma"
    mock_vs.return_value = mock_vs_instance

    tool = IndexPaperTool()
    result = tool.execute(paper_id="paper_A")
    assert result.success
    assert result.data["chunks_indexed"] == 2


@patch("app.agents.tools.paper_tools.load_parsed_result")
def test_index_not_found(mock_load):
    mock_load.side_effect = FileNotFoundError("not found")

    tool = IndexPaperTool()
    result = tool.execute(paper_id="paper_404")
    assert not result.success
    assert "解析结果不存在" in result.error


# ── QATool ────────────────────────────────────────────────────────────────────


def test_qa_missing_question():
    tool = QATool()
    result = tool.execute()
    assert not result.success
    assert "缺少 question" in result.error


@patch("app.agents.tools.paper_tools.answer_question")
@patch("app.agents.tools.paper_tools.EmbeddingClient")
@patch("app.agents.tools.paper_tools.VectorStore")
@patch("app.agents.tools.paper_tools.LLMClient")
def test_qa_success(mock_llm, mock_vs, mock_emb, mock_answer):
    mock_answer.return_value = {
        "question": "核心创新点？",
        "answer": "创新点是 VLM 方法。",
        "sources": [
            {
                "paper_id": "paper_A",
                "title": "Paper A",
                "section": "Method",
                "content": "VLM method",
                "chunk_id": "chunk_001",
                "score": 0.95,
                "page_number": 2,
                "chunk_start": 0,
                "chunk_end": 10,
            }
        ],
    }

    tool = QATool()
    result = tool.execute(question="核心创新点？")

    assert result.success
    assert result.data["sources_count"] == 1


# ── ComparePapersTool ──────────────────────────────────────────────────────────


def test_compare_not_enough_papers():
    tool = ComparePapersTool()
    result = tool.execute(paper_ids=["paper_A"])
    assert not result.success
    assert "至少 2 篇" in result.error


def test_compare_too_many_papers():
    tool = ComparePapersTool()
    result = tool.execute(paper_ids=[f"p{i}" for i in range(6)])
    assert not result.success
    assert "最多支持 5 篇" in result.error


def test_compare_invalid_type():
    tool = ComparePapersTool()
    result = tool.execute(paper_ids="not_a_list")
    assert not result.success


@patch("app.agents.tools.paper_tools.compare_papers")
@patch("app.agents.tools.paper_tools.save_compare_result")
def test_compare_success(mock_save, mock_compare):
    mock_compare.return_value.markdown = "# Comparison"
    mock_compare.return_value.aspects = [MagicMock(), MagicMock()]
    mock_save.return_value = "/tmp/compare.md"

    tool = ComparePapersTool()
    result = tool.execute(paper_ids=["paper_A", "paper_B"])

    assert result.success
    assert result.data["aspects_count"] == 2


# ── ExportMarkdownTool ─────────────────────────────────────────────────────────


def test_export_no_args():
    tool = ExportMarkdownTool()
    result = tool.execute()
    assert not result.success
    assert "请提供" in result.error


def test_export_with_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "output.md")
        tool = ExportMarkdownTool()
        result = tool.execute(content="# Hello", output_path=filepath)

        assert result.success
        assert result.data["output_path"] == filepath
        with open(filepath, "r") as f:
            assert f.read() == "# Hello"
