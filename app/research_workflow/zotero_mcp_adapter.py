from __future__ import annotations
from app.mcp.tool_proxy import MCPToolProxy


class ZoteroMCPAdapter:
    """Adapter for Zotero MCP server."""

    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "zotero"
