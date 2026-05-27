import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.langchain_adapter import (
    _create_args_schema,
    convert_all_tools,
    convert_to_langchain_tool,
)
from app.agents.tools.base import BaseTool, ToolParameter, ToolResult
from app.agents.tools.paper_tools import QATool, UploadPaperTool


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo back the input message"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="message", type="string", description="Message to echo"),
            ToolParameter(
                name="repeat",
                type="integer",
                description="Repeat count",
                required=False,
            ),
        ]

    def execute(self, **kwargs) -> ToolResult:
        msg = kwargs.get("message", "")
        repeat = int(kwargs.get("repeat", 1))
        return ToolResult(success=True, data={"echo": msg * repeat})


class FailingTool(BaseTool):
    name = "failing"
    description = "Always fails"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [ToolParameter(name="input", type="string", description="Any input")]

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=False, error="Simulated failure")


# ── args schema generation ────────────────────────────────────────────────────


def test_create_args_schema_required_only():
    schema = _create_args_schema(EchoTool())
    fields = schema.model_fields
    assert "message" in fields
    assert "repeat" in fields
    # message is required → not Optional
    msg_field = fields["message"]
    # repeat is optional → should have None default


def test_create_args_schema_types():
    schema = _create_args_schema(EchoTool())
    fields = schema.model_fields
    msg_field = fields["message"]
    # Check the annotation
    annot = msg_field.annotation
    assert annot is str
    rep_field = fields["repeat"]
    # Optional[int] is represented as int | None
    rep_annot = rep_field.annotation
    assert rep_annot == int | None


# ── single tool conversion ─────────────────────────────────────────────────────


def test_convert_qa_tool():
    lc_tool = convert_to_langchain_tool(QATool())
    assert lc_tool.name == "qa"
    assert "问答检索" in lc_tool.description


def test_convert_and_call_success():
    lc_tool = convert_to_langchain_tool(EchoTool())
    result = lc_tool.invoke({"message": "hello", "repeat": 2})
    assert '"echo": "hellohello"' in result


def test_convert_and_call_failure():
    lc_tool = convert_to_langchain_tool(FailingTool())
    result = lc_tool.invoke({"input": "test"})
    assert "工具执行失败" in result
    assert "Simulated failure" in result


# ── batch conversion ───────────────────────────────────────────────────────────


def test_convert_all_tools():
    tools = [UploadPaperTool(), QATool()]
    lc_tools = convert_all_tools(tools)
    assert len(lc_tools) == 2
    names = [t.name for t in lc_tools]
    assert "upload_paper" in names
    assert "qa" in names
