from __future__ import annotations

import os
import threading
import time
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Semantic Scholar")

# ---------------------------------------------------------------------------
# Rate limiting — 1 request / second across all endpoints (official policy)
# ---------------------------------------------------------------------------
_min_interval = 1.0  # seconds — must not be lowered even with an API key
_last_request_time = 0.0
_rate_lock = threading.Lock()


def _wait_for_rate_limit() -> None:
    """Block until at least 1 second has passed since the last API request.

    Semantic Scholar enforces 1 req/s cumulative across all endpoints,
    regardless of whether an API key is provided.  We honour this on the
    client side so that multi-threaded callers never exceed the quota.
    """
    global _last_request_time
    with _rate_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < _min_interval:
            time.sleep(_min_interval - elapsed)
        _last_request_time = time.time()


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------
_api_key: str | None = None


def _get_api_key() -> str | None:
    """Return the Semantic Scholar API key, if configured.

    Reads from, in order of priority:
      1. Environment variable ``SEMANTIC_SCHOLAR_API_KEY``
      2. ``app.config.settings.semantic_scholar_api_key`` (lazy import so the
         MCP server can still run as a stand-alone stdio process without the
         full app stack)
    """
    global _api_key
    if _api_key is not None:
        return _api_key or None

    env_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if env_key:
        _api_key = env_key
        return _api_key

    try:
        from app.config import settings  # type: ignore[import-untyped]

        cfg_key = getattr(settings, "semantic_scholar_api_key", "").strip()
        if cfg_key:
            _api_key = cfg_key
            return _api_key
    except Exception:
        pass

    _api_key = ""
    return None


def _build_headers() -> dict[str, str]:
    """Build HTTP headers including the API key when available."""
    headers: dict[str, str] = {"Accept": "application/json"}
    api_key = _get_api_key()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool(name="semantic_scholar_search")
def semantic_scholar_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Search for papers on Semantic Scholar by keyword."""
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
            headers=_build_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "query": query,
            "papers": [],
            "fallback_used": True,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
        }
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
        "total": data.get("total"),
        "fallback_used": False,
    }


@mcp.tool(name="semantic_scholar_get_paper")
def semantic_scholar_get_paper(paper_id: str) -> dict[str, Any]:
    """Get detailed information for a single paper by its ID.

    Accepts Semantic Scholar paper ID, DOI (prefix with ``DOI:``),
    or arXiv ID (prefix with ``ARXIV:``).
    """
    safe_id = quote(paper_id, safe="")
    params = {
        "fields": (
            "paperId,title,abstract,year,citationCount,referenceCount,"
            "url,authors,references,citations,externalIds,venue,"
            "publicationDate,openAccessPdf,fieldsOfStudy"
        ),
    }
    try:
        _wait_for_rate_limit()
        response = httpx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{safe_id}",
            params=params,
            headers=_build_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        paper = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "paper_id": paper_id,
            "paper": None,
            "fallback_used": True,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
        }
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


@mcp.tool(name="semantic_scholar_get_citations")
def semantic_scholar_get_citations(
    paper_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Get papers that cite a given paper."""
    safe_id = quote(paper_id, safe="")
    params = {
        "fields": "paperId,title,year,citationCount,authors,url",
        "limit": max(1, min(int(limit), 100)),
    }
    try:
        _wait_for_rate_limit()
        response = httpx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{safe_id}/citations",
            params=params,
            headers=_build_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "paper_id": paper_id,
            "citations": [],
            "fallback_used": True,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
        }
    except Exception as exc:
        return {
            "paper_id": paper_id,
            "citations": [],
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "paper_id": paper_id,
        "citations": data.get("data", []),
        "fallback_used": False,
    }


@mcp.tool(name="semantic_scholar_get_references")
def semantic_scholar_get_references(
    paper_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Get papers referenced by a given paper."""
    safe_id = quote(paper_id, safe="")
    params = {
        "fields": "paperId,title,year,citationCount,authors,url",
        "limit": max(1, min(int(limit), 100)),
    }
    try:
        _wait_for_rate_limit()
        response = httpx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{safe_id}/references",
            params=params,
            headers=_build_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "paper_id": paper_id,
            "references": [],
            "fallback_used": True,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
        }
    except Exception as exc:
        return {
            "paper_id": paper_id,
            "references": [],
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "paper_id": paper_id,
        "references": data.get("data", []),
        "fallback_used": False,
    }


@mcp.tool(name="semantic_scholar_get_author")
def semantic_scholar_get_author(author_id: str) -> dict[str, Any]:
    """Get author details by Semantic Scholar author ID."""
    safe_id = quote(author_id, safe="")
    params = {
        "fields": "name,affiliations,paperCount,citationCount,hIndex,url",
    }
    try:
        _wait_for_rate_limit()
        response = httpx.get(
            f"https://api.semanticscholar.org/graph/v1/author/{safe_id}",
            params=params,
            headers=_build_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        author = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "author_id": author_id,
            "author": None,
            "fallback_used": True,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
        }
    except Exception as exc:
        return {
            "author_id": author_id,
            "author": None,
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "author_id": author_id,
        "author": author,
        "fallback_used": False,
    }


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
