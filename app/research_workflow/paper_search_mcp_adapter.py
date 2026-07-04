from __future__ import annotations

from app.mcp.paper_normalizer import dedupe_papers, normalize_paper
from app.mcp.schemas import MCPToolCall, Paper
from app.mcp.tool_proxy import MCPToolProxy

# Default source mix for unified discovery: the two existing local sources
# plus the user-selected OpenAlex (broad metadata) and Crossref (DOI backbone).
DEFAULT_SOURCES = "arxiv,semantic,openalex,crossref"


class PaperSearchMCPAdapter:
    """Adapter over the external ``paper-search-mcp`` stdio MCP server.

    Exposes the server's aggregated ``search_papers`` and
    ``download_with_fallback`` tools, normalizing results to the unified
    :class:`Paper` model and deduplicating across sources. Sci-Hub is never
    used (``use_scihub=False``) for compliance.
    """

    SERVER_NAME = "paper-search"

    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy

    def search_papers(
        self,
        query: str,
        sources: str = DEFAULT_SOURCES,
        max_results_per_source: int = 5,
        year: str | None = None,
    ) -> list[Paper]:
        """Search across multiple sources and return deduplicated Papers."""
        arguments: dict = {
            "query": query,
            "max_results_per_source": max_results_per_source,
            "sources": sources,
        }
        if year:
            arguments["year"] = year

        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self.SERVER_NAME,
                tool_name="search_papers",
                arguments=arguments,
            )
        )
        if result.status != "success":
            return []

        payload = result.result if isinstance(result.result, dict) else {}
        raw_papers = payload.get("papers", [])
        if not isinstance(raw_papers, list):
            return []

        normalized = [normalize_paper(p) for p in raw_papers if isinstance(p, dict)]
        return dedupe_papers(normalized)

    def download(
        self,
        paper_id: str,
        source: str,
        doi: str = "",
        title: str = "",
        save_path: str = "./downloads",
    ) -> str:
        """Download a paper PDF via the OA fallback chain (Sci-Hub disabled).

        Returns the local PDF path on success or an explanatory error message.
        """
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self.SERVER_NAME,
                tool_name="download_with_fallback",
                arguments={
                    "source": source,
                    "paper_id": paper_id,
                    "doi": doi,
                    "title": title,
                    "save_path": save_path,
                    "use_scihub": False,
                },
            )
        )
        if result.status != "success":
            return f"download failed: {result.error or 'unknown error'}"

        # download_with_fallback returns a str (path or error message)
        return result.result if isinstance(result.result, str) else str(result.result)
