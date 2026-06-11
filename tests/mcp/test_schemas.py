import pytest
from pydantic import ValidationError

from app.mcp.schemas import MCPServerConfig, MCPToolCall, MCPToolResult


def test_mcp_server_config():
    config = MCPServerConfig(
        name="test", command=["test-mcp"], env={"KEY": "value"}
    )
    assert config.name == "test"
    assert config.auto_restart is True


def test_mcp_server_config_empty_command():
    with pytest.raises(ValidationError):
        MCPServerConfig(name="test", command=[])


def test_mcp_server_config_invalid_name():
    with pytest.raises(ValidationError):
        MCPServerConfig(name="invalid name!", command=["test"])


def test_mcp_tool_call():
    call = MCPToolCall(
        server_name="zotero", tool_name="search", arguments={"q": "test"}
    )
    assert call.server_name == "zotero"


def test_mcp_tool_result_success():
    result = MCPToolResult(
        status="success", result={"data": "ok"},
        duration_ms=50.0, server_name="zotero", tool_name="search"
    )
    assert result.status == "success"
    assert result.error is None


def test_mcp_tool_result_error_requires_error_field():
    with pytest.raises(ValueError):
        MCPToolResult(
            status="error", duration_ms=50.0,
            server_name="zotero", tool_name="search"
        )
