from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPToolCall, MCPToolResult


class MCPToolProxy:
    """Unified interface for calling MCP tools."""

    def __init__(self, client_manager: MCPClientManager):
        self._manager = client_manager

    def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        """Call an MCP tool and normalize transport/tool errors."""
        started = datetime.now(timezone.utc)
        try:
            result = self._manager.call_tool(
                call.server_name,
                call.tool_name,
                call.arguments,
                timeout_seconds=settings.mcp_tool_timeout,
            )
        except TimeoutError as exc:
            return MCPToolResult(
                status="timeout",
                result=None,
                error=str(exc),
                duration_ms=_duration_ms(started),
                server_name=call.server_name,
                tool_name=call.tool_name,
            )
        except Exception as exc:
            return MCPToolResult(
                status="error",
                result=None,
                error=str(exc),
                duration_ms=_duration_ms(started),
                server_name=call.server_name,
                tool_name=call.tool_name,
            )

        return MCPToolResult(
            status="success",
            result=result,
            error=None,
            duration_ms=_duration_ms(started),
            server_name=call.server_name,
            tool_name=call.tool_name,
        )

    def list_available_tools(self) -> dict[str, list[str]]:
        tools: dict[str, list[str]] = {}
        for server_name in self._manager.list_servers():
            tools[server_name] = self._manager.list_tools(server_name)
        return tools


def _duration_ms(started: datetime) -> float:
    return (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
