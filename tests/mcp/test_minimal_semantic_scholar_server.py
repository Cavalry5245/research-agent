"""Tests for the minimal Semantic Scholar MCP server and its adapter."""

from __future__ import annotations

from unittest.mock import patch

from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolResult
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.semantic_scholar_mcp_adapter import SemanticScholarMCPAdapter


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


def test_semantic_scholar_mcp_server_exposes_tools():
    manager = MCPClientManager()
    server_config = MCPServerConfig(
        name="semantic-scholar",
        command=["python", "-m", "app.mcp.minimal_semantic_scholar_server"],
    )
    manager.start_server(server_config)
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "semantic_scholar_search" in tools["semantic-scholar"]
    assert "semantic_scholar_get_paper" in tools["semantic-scholar"]
    assert "semantic_scholar_get_citations" in tools["semantic-scholar"]
    assert "semantic_scholar_get_references" in tools["semantic-scholar"]
    assert "semantic_scholar_get_author" in tools["semantic-scholar"]


# ---------------------------------------------------------------------------
# API key via environment variable
# ---------------------------------------------------------------------------


def test_server_sends_api_key_in_headers():
    """When SEMANTIC_SCHOLAR_API_KEY is set, the x-api-key header must be sent."""
    from app.mcp.minimal_semantic_scholar_server import _build_headers, _get_api_key

    with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key-123"}, clear=True):
        # Reset cached key
        from app.mcp import minimal_semantic_scholar_server as ss

        ss._api_key = None  # type: ignore[attr-defined]

        assert _get_api_key() == "test-key-123"
        headers = _build_headers()
        assert headers.get("x-api-key") == "test-key-123"


def test_server_skips_api_key_when_not_set():
    """When no API key is configured, the x-api-key header must be absent."""
    from app.mcp.minimal_semantic_scholar_server import _build_headers, _get_api_key

    with patch.dict("os.environ", {}, clear=True):
        from app.mcp import minimal_semantic_scholar_server as ss

        ss._api_key = None  # type: ignore[attr-defined]

        # Mock app.config.settings so the lazy import inside _get_api_key()
        # doesn't read the real .env file
        with patch("app.config.settings") as mock_settings:
            mock_settings.semantic_scholar_api_key = ""
            assert _get_api_key() is None

        headers = _build_headers()
        assert "x-api-key" not in headers


def test_server_falls_back_to_settings_config():
    """If env var is missing, falls back to app.config.settings."""
    from app.mcp import minimal_semantic_scholar_server as ss

    ss._api_key = None  # type: ignore[attr-defined]

    with patch.dict("os.environ", {}, clear=True):
        with patch("app.config.settings") as mock_settings:
            mock_settings.semantic_scholar_api_key = "cfg-key-456"
            from app.mcp import minimal_semantic_scholar_server as ss

            ss._api_key = None  # type: ignore[attr-defined]
            key = ss._get_api_key()
            assert key == "cfg-key-456"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def test_rate_limit_enforces_one_second_interval():
    """Must block for at least 1 second between consecutive requests."""
    from app.mcp import minimal_semantic_scholar_server as ss

    import time

    ss._last_request_time = 0.0  # type: ignore[attr-defined]

    t0 = time.perf_counter()
    ss._wait_for_rate_limit()  # first call — no wait
    t1 = time.perf_counter()
    assert t1 - t0 < 0.5, "First call should return immediately"

    ss._wait_for_rate_limit()  # second call — must wait ~1 s
    t2 = time.perf_counter()
    assert t2 - t1 >= 0.9, f"Second call should wait ~1s (was {t2 - t1:.3f}s)"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


def test_semantic_scholar_adapter_returns_papers_from_proxy():
    class FakeProxy:
        def call_tool(self, call):
            assert call.server_name == "semantic-scholar"
            assert call.tool_name == "semantic_scholar_search"
            assert call.arguments == {"query": "agentic rag", "limit": 2}
            return MCPToolResult(
                status="success",
                result={
                    "query": "agentic rag",
                    "papers": [{"paperId": "P1", "title": "Agentic RAG"}],
                    "fallback_used": False,
                },
                duration_ms=1.0,
                server_name="semantic-scholar",
                tool_name="semantic_scholar_search",
            )

    adapter = SemanticScholarMCPAdapter(FakeProxy())

    assert adapter.search_papers("agentic rag", limit=2) == [
        {"paperId": "P1", "title": "Agentic RAG"}
    ]
