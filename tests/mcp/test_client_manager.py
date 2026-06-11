from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig


def test_manager_init():
    manager = MCPClientManager()
    assert manager is not None
    assert len(manager.list_servers()) == 0


def test_start_mock_server(tmp_path):
    # Create a mock server script
    mock_script = tmp_path / "mock_mcp.py"
    mock_script.write_text("""
import sys
import time
while True:
    time.sleep(0.1)
""")

    manager = MCPClientManager()
    config = MCPServerConfig(
        name="test",
        command=["python", str(mock_script)]
    )

    manager.start_server(config)
    assert "test" in manager.list_servers()

    server = manager.get_server("test")
    assert server.is_running()

    manager.shutdown_all()


def test_stop_server(tmp_path):
    mock_script = tmp_path / "mock.py"
    mock_script.write_text("import time\nwhile True: time.sleep(0.1)")

    manager = MCPClientManager()
    config = MCPServerConfig(name="test", command=["python", str(mock_script)])

    manager.start_server(config)
    assert "test" in manager.list_servers()

    manager.stop_server("test")
    assert "test" not in manager.list_servers()
