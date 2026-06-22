from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Semantic Scholar")

# Rate limiting: 1 request per second for unauthenticated access
_last_request_time = 0
_min_interval = 1.0  # seconds


def _wait_for_rate_limit():
    """Ensure at least 1 second between requests to Semantic Scholar API."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _min_interval:
        time.sleep(_min_interval - elapsed)
    _last_request_time = time.time()


@mcp.tool(name="semantic_scholar_search")
def semantic_scholar_search(query: str, limit: int = 5) -> dict[str, Any]:
    params = {
        "query": query,
        "limit": max(1, min(int(limit), 20)),
        "fields": "paperId,title,abstract,year,citationCount,referenceCount,url,authors",
    }
    try:
        _wait_for_rate_limit()
        response = httpx.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {
            "query": query,
            "papers": [],
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "query": query,
        "papers": data.get("data", []),
        "fallback_used": False,
    }


@mcp.tool(name="semantic_scholar_get_paper")
def semantic_scholar_get_paper(paper_id: str) -> dict[str, Any]:
    safe_id = quote(paper_id, safe="")
    params = {
        "fields": "paperId,title,abstract,year,citationCount,referenceCount,url,authors,references,citations",
    }
    try:
        _wait_for_rate_limit()
        response = httpx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{safe_id}",
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        paper = response.json()
    except Exception as exc:
        return {
            "paper_id": paper_id,
            "paper": None,
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "paper_id": paper_id,
        "paper": paper,
        "fallback_used": False,
    }


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
