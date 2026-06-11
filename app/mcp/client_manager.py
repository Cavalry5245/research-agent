from __future__ import annotations
import subprocess
import threading
from typing import Any
from pathlib import Path

from app.mcp.schemas import MCPServerConfig


class MCPServerProcess:
    """Represents a running MCP server process."""

    def __init__(self, config: MCPServerConfig, process: subprocess.Popen):
        self.config = config
        self.process = process
        self.is_healthy = True

    def is_running(self) -> bool:
        return self.process.poll() is None


class MCPClientManager:
    """Manages lifecycle of MCP server processes."""

    def __init__(self):
        self._servers: dict[str, MCPServerProcess] = {}
        self._lock = threading.Lock()

    def list_servers(self) -> list[str]:
        with self._lock:
            return list(self._servers.keys())

    def get_server(self, name: str) -> MCPServerProcess | None:
        with self._lock:
            return self._servers.get(name)

    def start_server(self, config: MCPServerConfig) -> MCPServerProcess:
        import os

        with self._lock:
            if config.name in self._servers:
                raise ValueError(f"Server {config.name} already exists")

            # Start subprocess
            process = subprocess.Popen(
                config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={**os.environ, **config.env},
                cwd=config.cwd
            )

            server = MCPServerProcess(config, process)
            self._servers[config.name] = server
            return server

    def stop_server(self, name: str) -> None:
        with self._lock:
            server = self._servers.get(name)
            if server is None:
                raise ValueError(f"Server {name} not found")
            del self._servers[name]

        if server.is_running():
            server.process.terminate()
            try:
                server.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.process.kill()
                server.process.wait()

    def shutdown_all(self) -> None:
        with self._lock:
            servers = list(self._servers.values())
            self._servers.clear()

        for server in servers:
            if server.is_running():
                server.process.terminate()
                try:
                    server.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.process.kill()
                    server.process.wait()
