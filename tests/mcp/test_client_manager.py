from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig


def test_manager_init():
    manager = MCPClientManager()
    assert manager is not None
    assert len(manager.list_servers()) == 0
