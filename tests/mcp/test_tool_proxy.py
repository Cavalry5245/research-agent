from app.mcp.tool_proxy import MCPToolProxy
from app.mcp.client_manager import MCPClientManager


def test_proxy_init():
    manager = MCPClientManager()
    proxy = MCPToolProxy(manager)
    assert proxy is not None
