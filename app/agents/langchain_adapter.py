import json
import logging

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.agents.tools.base import BaseTool

logger = logging.getLogger(__name__)


def _create_args_schema(tool: BaseTool) -> type[BaseModel]:
    """Dynamically create a Pydantic model from BaseTool parameters."""
    fields: dict[str, tuple[type, object]] = {}
    for p in tool.parameters:
        py_type: type = str
        if p.type in ("integer", "int"):
            py_type = int
        elif p.type == "number":
            py_type = float
        elif p.type == "array":
            py_type = list
        elif p.type == "boolean":
            py_type = bool

        if p.required:
            fields[p.name] = (py_type, Field(description=p.description))
        else:
            fields[p.name] = (
                py_type | None,
                Field(default=None, description=p.description),
            )

    return create_model(f"{tool.name}_schema", **fields)  # type: ignore[call-overload]


def convert_to_langchain_tool(tool: BaseTool) -> StructuredTool:
    """
    Convert a project BaseTool into a LangChain StructuredTool.

    The adapter maps:
    - tool.name → StructuredTool.name
    - tool.description → StructuredTool.description
    - tool.parameters → Pydantic args_schema (dynamically generated)
    - tool.execute   → StructuredTool.func
    """
    args_schema = _create_args_schema(tool)

    def _execute(**kwargs) -> str:
        result = tool.execute(**kwargs)
        if result.success:
            return json.dumps(result.data, ensure_ascii=False, indent=2)
        return f"工具执行失败: {result.error}"

    # Strip help text from description to keep it clean
    description = tool.description
    if "。" in description:
        description = description.split("。")[0]

    return StructuredTool(
        name=tool.name,
        description=description,
        args_schema=args_schema,
        func=_execute,
    )


def convert_all_tools(tools: list[BaseTool]) -> list[StructuredTool]:
    """Convert a list of BaseTool instances to LangChain StructuredTool instances."""
    return [convert_to_langchain_tool(t) for t in tools]