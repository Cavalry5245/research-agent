import asyncio

import pytest

from app.mcp.schemas import MCPServerConfig
from app.mcp.stdio_session import StdioMCPSession


def test_stdio_mcp_session_lists_and_calls_tools():
    asyncio.run(_assert_stdio_mcp_session_lists_and_calls_tools())


async def _assert_stdio_mcp_session_lists_and_calls_tools():
    session = StdioMCPSession(
        MCPServerConfig(
            name="mock",
            command=["python", "-m", "app.mcp.mock_server"],
        )
    )
    await session.start()
    try:
        tools = await session.list_tools()
        assert "mock_echo" in tools

        result = await session.call_tool("mock_echo", {"message": "hello"})
        assert result == {"message": "hello"}
    finally:
        await session.stop()
