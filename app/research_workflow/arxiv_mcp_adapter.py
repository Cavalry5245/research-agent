from __future__ import annotations

from app.mcp.schemas import MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


class ArxivMCPAdapter:
    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "arxiv"

    def search_papers(self, query: str, max_results: int = 10) -> list[dict]:
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self._server_name,
                tool_name="arxiv_search",
                arguments={"query": query, "max_results": max_results},
            )
        )
        if result.status != "success":
            return []
        payload = result.result if isinstance(result.result, dict) else {}
        papers = payload.get("papers", [])
        return papers if isinstance(papers, list) else []
