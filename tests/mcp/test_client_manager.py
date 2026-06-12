from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig


def test_manager_init():
    manager = MCPClientManager()
    try:
        assert manager.list_servers() == []
    finally:
        manager.shutdown_all()


def test_start_mock_server():
    manager = MCPClientManager()
    config = MCPServerConfig(
        name="mock",
        command=["python", "-m", "app.mcp.mock_server"],
    )

    manager.start_server(config)
    try:
        assert "mock" in manager.list_servers()
        assert manager.get_server("mock").is_running()
    finally:
        manager.shutdown_all()


def test_stop_server():
    manager = MCPClientManager()
    config = MCPServerConfig(
        name="mock",
        command=["python", "-m", "app.mcp.mock_server"],
    )

    manager.start_server(config)
    manager.stop_server("mock")
    try:
        assert manager.list_servers() == []
    finally:
        manager.shutdown_all()


def test_manager_lists_tools_from_mock_server():
    manager = MCPClientManager()
    config = MCPServerConfig(
        name="mock",
        command=["python", "-m", "app.mcp.mock_server"],
    )

    manager.start_server(config)
    try:
        assert "mock_echo" in manager.list_tools("mock")
    finally:
        manager.shutdown_all()


def test_manager_returns_existing_session_when_started_twice():
    manager = MCPClientManager()
    config = MCPServerConfig(
        name="mock",
        command=["python", "-m", "app.mcp.mock_server"],
    )

    first = manager.start_server(config)
    second = manager.start_server(config)
    try:
        assert first is second
        assert manager.list_servers() == ["mock"]
    finally:
        manager.shutdown_all()
