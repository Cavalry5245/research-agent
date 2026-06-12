from __future__ import annotations

from app.mcp.schemas import MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


class SemanticScholarMCPAdapter:
    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "semantic-scholar"

    def search_papers(self, query: str, limit: int = 10) -> list[dict]:
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self._server_name,
                tool_name="semantic_scholar_search",
                arguments={"query": query, "limit": limit},
            )
        )
        if result.status != "success":
            return []
        payload = result.result if isinstance(result.result, dict) else {}
        papers = payload.get("papers", [])
        return papers if isinstance(papers, list) else []

    def get_paper(self, paper_id: str) -> dict | None:
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self._server_name,
                tool_name="semantic_scholar_get_paper",
                arguments={"paper_id": paper_id},
            )
        )
        if result.status != "success":
            return None
        payload = result.result if isinstance(result.result, dict) else {}
        paper = payload.get("paper")
        return paper if isinstance(paper, dict) else None
