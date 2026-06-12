from app.mcp.client_manager import MCPClientManager
from app.mcp.minimal_arxiv_server import _parse_arxiv_feed
from app.mcp.schemas import MCPServerConfig, MCPToolResult
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.arxiv_mcp_adapter import ArxivMCPAdapter


def test_arxiv_mcp_server_exposes_search_tool():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="arxiv",
            command=["python", "-m", "app.mcp.minimal_arxiv_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "arxiv_search" in tools["arxiv"]


def test_parse_arxiv_feed_returns_deterministic_paper_fields():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <updated>2024-01-02T00:00:00Z</updated>
    <published>2024-01-01T00:00:00Z</published>
    <title>  A Paper
      About Agents </title>
    <summary>  This paper studies
      agent systems. </summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Grace Hopper</name></author>
    <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.00001v1" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""

    papers = _parse_arxiv_feed(xml)

    assert papers == [
        {
            "id": "http://arxiv.org/abs/2401.00001v1",
            "title": "A Paper About Agents",
            "authors": ["Ada Lovelace", "Grace Hopper"],
            "abstract": "This paper studies agent systems.",
            "url": "http://arxiv.org/abs/2401.00001v1",
            "pdf_url": "http://arxiv.org/pdf/2401.00001v1",
            "published": "2024-01-01T00:00:00Z",
            "updated": "2024-01-02T00:00:00Z",
        }
    ]


def test_arxiv_adapter_returns_papers_from_proxy():
    class FakeProxy:
        def call_tool(self, call):
            assert call.server_name == "arxiv"
            assert call.tool_name == "arxiv_search"
            assert call.arguments == {"query": "agentic rag", "max_results": 2}
            return MCPToolResult(
                status="success",
                result={
                    "query": "agentic rag",
                    "papers": [{"id": "http://arxiv.org/abs/2401.00001", "title": "Agentic RAG"}],
                    "fallback_used": False,
                },
                duration_ms=1.0,
                server_name="arxiv",
                tool_name="arxiv_search",
            )

    adapter = ArxivMCPAdapter(FakeProxy())

    assert adapter.search_papers("agentic rag", max_results=2) == [
        {"id": "http://arxiv.org/abs/2401.00001", "title": "Agentic RAG"}
    ]
