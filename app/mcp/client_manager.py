from __future__ import annotations

import threading
from typing import Any

from app.mcp.schemas import MCPServerConfig
from app.mcp.stdio_session import MCPEventLoopThread, StdioMCPSession


class MCPManagedServer:
    """Represents a running MCP server session."""

    def __init__(self, config: MCPServerConfig, session: StdioMCPSession):
        self.config = config
        self.session = session

    def is_running(self) -> bool:
        return self.session.is_started


class MCPClientManager:
    """Manages lifecycle of MCP server sessions."""

    def __init__(self):
        self._servers: dict[str, MCPManagedServer] = {}
        self._lock = threading.Lock()
        self._loop = MCPEventLoopThread()

    def list_servers(self) -> list[str]:
        with self._lock:
            return list(self._servers.keys())

    def get_server(self, name: str) -> MCPManagedServer | None:
        with self._lock:
            return self._servers.get(name)

    def start_server(self, config: MCPServerConfig) -> MCPManagedServer:
        with self._lock:
            existing = self._servers.get(config.name)
            if existing is not None and existing.is_running():
                return existing

        session = StdioMCPSession(config)
        self._loop.run(session.start())
        server = MCPManagedServer(config, session)

        with self._lock:
            self._servers[config.name] = server
        return server

    def stop_server(self, name: str) -> None:
        with self._lock:
            server = self._servers.pop(name, None)
        if server is None:
            raise ValueError(f"Server {name} not found")
        self._loop.run(server.session.stop())

    def shutdown_all(self) -> None:
        with self._lock:
            servers = list(self._servers.values())
            self._servers.clear()

        for server in servers:
            self._loop.run(server.session.stop())
        self._loop.stop()

    def list_tools(self, server_name: str) -> list[str]:
        server = self._require_server(server_name)
        return self._loop.run(server.session.list_tools())

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        server = self._require_server(server_name)
        return self._loop.run(
            server.session.call_tool(
                tool_name,
                arguments or {},
                timeout_seconds=timeout_seconds,
            )
        )

    def _require_server(self, server_name: str) -> MCPManagedServer:
        with self._lock:
            server = self._servers.get(server_name)
        if server is None or not server.is_running():
            raise ValueError(f"MCP server is not running: {server_name}")
        return server
