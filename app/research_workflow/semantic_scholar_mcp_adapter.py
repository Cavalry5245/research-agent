from __future__ import annotations
from app.mcp.tool_proxy import MCPToolProxy


class SemanticScholarMCPAdapter:
    """Adapter for Semantic Scholar MCP server (stub)."""

    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "semantic-scholar"

    def search_papers(self, query: str, limit: int = 10) -> list[dict]:
        """Search papers via MCP (stub).

        TODO: Implement when MCP server available.
        """
        return []
