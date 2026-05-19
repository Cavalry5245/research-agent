import logging

from app.agents.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError(f"Tool must have a name: {type(tool).__name__}")
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def list_tool_definitions(self) -> list[dict]:
        return [t.to_dict() for t in self._tools.values()]

    def register_all(self, tools: list[BaseTool]) -> None:
        for tool in tools:
            self.register(tool)
