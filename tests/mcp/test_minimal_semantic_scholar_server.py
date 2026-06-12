from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolResult
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.semantic_scholar_mcp_adapter import SemanticScholarMCPAdapter


def test_semantic_scholar_mcp_server_exposes_tools():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="semantic-scholar",
            command=["python", "-m", "app.mcp.minimal_semantic_scholar_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "semantic_scholar_search" in tools["semantic-scholar"]
    assert "semantic_scholar_get_paper" in tools["semantic-scholar"]


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
