from __future__ import annotations
import logging
from app.mcp.tool_proxy import MCPToolProxy

logger = logging.getLogger(__name__)


class ArxivMCPAdapter:
    """Adapter for arXiv MCP server (stub)."""

    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "arxiv"

    def search_papers(self, query: str, max_results: int = 10) -> list[dict]:
        """Search papers via MCP (stub).

        TODO: Implement when MCP server available.
        """
        logger.warning(f"ArxivMCPAdapter.search_papers is a stub (query={query})")
        return []
