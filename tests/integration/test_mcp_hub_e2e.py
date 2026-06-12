from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


def test_mcp_hub_can_call_three_servers():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="mock",
            command=["python", "-m", "app.mcp.mock_server"],
        )
    )
    manager.start_server(
        MCPServerConfig(
            name="semantic-scholar",
            command=["python", "-m", "app.mcp.minimal_semantic_scholar_server"],
        )
    )
    manager.start_server(
        MCPServerConfig(
            name="arxiv",
            command=["python", "-m", "app.mcp.minimal_arxiv_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
        echo = proxy.call_tool(
            MCPToolCall(
                server_name="mock",
                tool_name="mock_echo",
                arguments={"message": "hub"},
            )
        )
    finally:
        manager.shutdown_all()

    assert "mock_echo" in tools["mock"]
    assert "semantic_scholar_search" in tools["semantic-scholar"]
    assert "arxiv_search" in tools["arxiv"]
    assert echo.status == "success"
    assert echo.result == {"message": "hub"}
