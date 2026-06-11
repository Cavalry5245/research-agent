from __future__ import annotations
from typing import Any
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPToolCall, MCPToolResult


class MCPToolProxy:
    """Unified interface for calling MCP tools."""

    def __init__(self, client_manager: MCPClientManager):
        self._manager = client_manager
