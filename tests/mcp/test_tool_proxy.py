from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


def test_proxy_init():
    manager = MCPClientManager()
    try:
        proxy = MCPToolProxy(manager)
        assert proxy is not None
    finally:
        manager.shutdown_all()


def test_proxy_calls_mcp_tool():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="mock",
            command=["python", "-m", "app.mcp.mock_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        result = proxy.call_tool(
            MCPToolCall(
                server_name="mock",
                tool_name="mock_echo",
                arguments={"message": "hello"},
            )
        )
    finally:
        manager.shutdown_all()

    assert result.status == "success"
    assert result.result == {"message": "hello"}
    assert result.error is None
    assert result.duration_ms >= 0


def test_proxy_normalizes_tool_error():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="mock",
            command=["python", "-m", "app.mcp.mock_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        result = proxy.call_tool(
            MCPToolCall(server_name="mock", tool_name="mock_fail")
        )
    finally:
        manager.shutdown_all()

    assert result.status == "error"
    assert "mock failure" in result.error


def test_proxy_lists_available_tools():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="mock",
            command=["python", "-m", "app.mcp.mock_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert tools == {"mock": ["mock_echo", "mock_fail"]}
