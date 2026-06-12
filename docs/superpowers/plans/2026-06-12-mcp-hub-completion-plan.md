# MCP Hub Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete ResearchAgent from a working local Zotero-to-Knowledge-Pack workflow into a demonstrable MCP Hub product where ResearchAgent can call external MCP tools, expose its own tools through a standard MCP server, and keep the existing local fallbacks reliable.

**Architecture:** Use an Agent-as-MCP-client pattern for external tools and a ResearchAgent-as-MCP-server pattern for exposing internal workflow capabilities. Zotero MCP becomes the preferred intake path, Zotero local HTTP remains the fallback, Semantic Scholar and arXiv get minimal local MCP servers, and Obsidian remains direct Markdown first with an explicit MCP extension point.

**Tech Stack:** Python 3.11, FastAPI, Streamlit, Pydantic v2, `mcp`, stdio MCP transport, `httpx`, Zotero local API, local Markdown publishing.

---

## Current State Summary

The project already has a usable local research workflow:

- Zotero local API is available on `127.0.0.1:23119`.
- `zotero-cli get collections --limit 10` can read the user's Zotero collections.
- `ResearchRunService.execute_local_run()` can run a Zotero collection intake using `ZoteroLocalHttpClient`.
- Knowledge Pack files, trace JSON, and `tool-calls.jsonl` are generated.
- `ResearchAgentMCPServer` exists as an internal FastAPI facade at `/research-runs/tools/call`.
- `app/mcp/` exists, but it is not yet a real MCP protocol client.

The product is therefore currently a working local research workflow with MCP-flavored naming. To become a complete MCP Hub demo, it must add real MCP protocol calls, real external MCP server wiring, a standard ResearchAgent MCP server entry point, visible health/state, and end-to-end tests.

---

## Supplemental Requirements

### R1. Standard MCP Client Layer

ResearchAgent must be able to start stdio MCP servers, initialize `mcp.ClientSession`, list tools, call tools, normalize responses, and shut everything down cleanly.

Acceptance criteria:

- `MCPClientManager.start_server()` creates a live stdio MCP session, not only a subprocess.
- `MCPClientManager.list_tools(server_name)` returns tool names from a real MCP server.
- `MCPToolProxy.call_tool()` calls `ClientSession.call_tool()` and returns `MCPToolResult`.
- Timeout, missing server, tool errors, and process startup failures are normalized.
- Unit tests use a local mock MCP server and do not require Zotero.

### R2. Zotero MCP As Primary Intake

Collection intake must prefer Zotero MCP and automatically fall back to Zotero local HTTP if MCP startup, tool discovery, or tool call parsing fails.

Acceptance criteria:

- `ZoteroMCPAdapter.list_collection_items(collection_id)` calls a real Zotero MCP tool.
- It maps MCP output into `ZoteroCollectionItem`.
- `CollectionIntakeService` accepts either MCP or HTTP client through the existing `ZoteroCollectionClient` protocol.
- `ResearchRunService` chooses MCP when available and local HTTP otherwise.
- Tests prove fallback happens when MCP returns an error.

### R3. Correct Zotero MCP Installation And Command Resolution

The project must stop trying to install the obsolete `zotero-mcp-server==0.1.0` package by default and must use the configured local executable first.

Acceptance criteria:

- `ZOTERO_MCP_COMMAND` is the preferred command.
- If unset, use `zotero-mcp` from `PATH`.
- `ensure_zotero_mcp_installed()` recognizes the editable `third_party/zotero-mcp` install.
- The auto-install path is opt-in and version-safe.
- Startup logs show the exact command used without printing secrets.

### R4. Minimal Semantic Scholar MCP Server

ResearchAgent must demonstrate a second external MCP tool path beyond Zotero. Semantic Scholar can be implemented as a minimal local MCP server wrapping the public API.

Acceptance criteria:

- A local stdio MCP server exposes `semantic_scholar_search` and `semantic_scholar_get_paper`.
- The adapter calls the server through `MCPToolProxy`.
- Network/API failure returns a structured fallback result, not a crash.
- Tests use mocked `httpx` or a fake server.

### R5. Minimal arXiv MCP Server

ResearchAgent must demonstrate a third external MCP tool path. arXiv can be implemented as a minimal local MCP server wrapping the Atom API.

Acceptance criteria:

- A local stdio MCP server exposes `arxiv_search`.
- The adapter calls the server through `MCPToolProxy`.
- XML parsing is deterministic and returns title, authors, abstract, URL, PDF URL, and published date.
- Tests use a fixed XML fixture.

### R6. ResearchAgent Standard MCP Server

ResearchAgent must expose its own capabilities through a standard MCP server, not only a FastAPI facade.

Acceptance criteria:

- A module can be started with `python -m app.research_workflow.mcp_stdio_server`.
- It exposes at least these tools: `research_agent_list_runs`, `research_agent_list_papers`, `research_agent_get_run_trace`, `research_agent_export_knowledge_pack`, `research_agent_search_chunks`, `research_agent_answer_question`, `research_agent_compare_papers`.
- Existing `ResearchAgentMCPServer` logic is reused instead of duplicated.
- An MCP client test can list and call at least one ResearchAgent tool over stdio.

### R7. Tool Registry And Trace Must Distinguish MCP From Fallbacks

Every tool call record must show whether it used MCP, direct HTTP, direct Markdown, local service, or fallback.

Acceptance criteria:

- `tool-calls.jsonl` records provider, status, duration, fallback flag, and a short result summary.
- Zotero MCP success records provider `zotero_mcp`.
- Zotero fallback records provider `local_http` and `fallback_used=true`.
- Semantic Scholar and arXiv records include `fallback_used` when external enrichment fails.

### R8. UI Must Show Real MCP Hub Status

The Streamlit app must show real status for configured MCP servers and fallbacks.

Acceptance criteria:

- UI shows each server: Zotero, Semantic Scholar, arXiv, ResearchAgent MCP.
- UI shows process/session state: running, unavailable, fallback active.
- UI shows discovered tool count when a server is connected.
- UI does not claim MCP availability when only local fallback is active.

### R9. End-to-End Demo Script And Verification

The repo must have a reproducible command sequence for the flagship demo.

Acceptance criteria:

- A documented demo can run: Zotero Collection -> MCP intake -> optional enrichment -> paper processing -> synthesis -> Obsidian-ready Knowledge Pack.
- The demo instructions include Zotero local API check, tests, app startup, and expected outputs.
- The verification commands run from `E:\projects\ResearchAgent` using `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe`.

---

## File Structure

### Existing Files To Modify

- `app/config.py`: add command parsing and flags for Semantic Scholar, arXiv, and ResearchAgent MCP server.
- `app/mcp/client_manager.py`: replace process-only lifecycle with stdio MCP session lifecycle.
- `app/mcp/tool_proxy.py`: implement synchronous and asynchronous tool calls.
- `app/mcp/installer.py`: fix Zotero MCP detection and command resolution.
- `app/mcp/schemas.py`: add health/status models and command normalization helpers.
- `app/research_workflow/service.py`: wire MCP-first Zotero intake and enrichment tools.
- `app/research_workflow/zotero_mcp_adapter.py`: implement real Zotero MCP calls and parsing.
- `app/research_workflow/semantic_scholar_mcp_adapter.py`: implement real MCP adapter.
- `app/research_workflow/arxiv_mcp_adapter.py`: implement real MCP adapter.
- `app/research_workflow/tool_adapters.py`: report accurate fallback status.
- `app/research_workflow/tool_registry.py`: preserve provider and fallback metadata.
- `app/research_workflow/mcp_server.py`: keep as domain facade used by FastAPI and stdio MCP server.
- `app/routers/research_runs.py`: expose MCP health using real manager state.
- `ui/streamlit_app.py`: display true MCP status.
- `requirements.txt`: keep `mcp`; add no unnecessary new runtime dependencies.
- `docs/RUN_GUIDE.md`: add MCP Hub demo runbook.
- `docs/JD_MCP_CAPABILITIES.md`: update capability claims to match implementation.

### New Files To Create

- `app/mcp/stdio_session.py`: async stdio MCP session wrapper.
- `app/mcp/mock_server.py`: local mock MCP server used by tests.
- `app/mcp/minimal_semantic_scholar_server.py`: minimal Semantic Scholar MCP server.
- `app/mcp/minimal_arxiv_server.py`: minimal arXiv MCP server.
- `app/research_workflow/mcp_stdio_server.py`: standard ResearchAgent MCP server entry point.
- `tests/mcp/test_stdio_session.py`: stdio session behavior.
- `tests/mcp/test_tool_proxy_call_tool.py`: proxy behavior and error normalization.
- `tests/mcp/test_minimal_semantic_scholar_server.py`: Semantic Scholar server behavior.
- `tests/mcp/test_minimal_arxiv_server.py`: arXiv server behavior.
- `tests/integration/test_mcp_hub_e2e.py`: real MCP flow with mock servers and local fallbacks.

---

## Phase 1: Real MCP Client Foundation

### Task 1: Add A Stdio MCP Session Wrapper

**Files:**

- Create: `app/mcp/stdio_session.py`
- Modify: `app/mcp/schemas.py`
- Test: `tests/mcp/test_stdio_session.py`

- [ ] **Step 1: Write a mock MCP server fixture**

Create `app/mcp/mock_server.py`:

```python
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ResearchAgent Mock MCP")


@mcp.tool(name="mock_echo")
def mock_echo(message: str) -> dict[str, str]:
    return {"message": message}


@mcp.tool(name="mock_fail")
def mock_fail() -> dict[str, str]:
    raise RuntimeError("mock failure")


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the failing session test**

Create `tests/mcp/test_stdio_session.py`:

```python
import pytest

from app.mcp.schemas import MCPServerConfig
from app.mcp.stdio_session import StdioMCPSession


@pytest.mark.asyncio
async def test_stdio_mcp_session_lists_and_calls_tools():
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_stdio_session.py -q
```

Expected: fails because `app.mcp.stdio_session` does not exist.

- [ ] **Step 4: Implement the session wrapper**

Create `app/mcp/stdio_session.py`:

```python
from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp.schemas import MCPServerConfig


class StdioMCPSession:
    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()

    @property
    def is_started(self) -> bool:
        return self._session is not None

    async def start(self) -> None:
        if self._session is not None:
            return

        stack = AsyncExitStack()
        params = StdioServerParameters(
            command=self.config.command[0],
            args=self.config.command[1:],
            env=self.config.env or None,
            cwd=self.config.cwd,
        )
        read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        self._exit_stack = stack
        self._session = session

    async def stop(self) -> None:
        stack = self._exit_stack
        self._exit_stack = None
        self._session = None
        if stack is not None:
            await stack.aclose()

    async def list_tools(self) -> list[str]:
        session = self._require_session()
        async with self._lock:
            result = await session.list_tools()
        return [tool.name for tool in result.tools]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        session = self._require_session()
        timeout = (
            timedelta(seconds=timeout_seconds)
            if timeout_seconds is not None
            else None
        )
        async with self._lock:
            result = await session.call_tool(
                tool_name,
                arguments or {},
                read_timeout_seconds=timeout,
            )
        if result.isError:
            text = _content_to_text(result.content)
            raise RuntimeError(text or f"MCP tool failed: {tool_name}")
        return _content_to_value(result.content)

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError(f"MCP server is not started: {self.config.name}")
        return self._session


def _content_to_value(content: Any) -> Any:
    if not content:
        return None
    if len(content) == 1:
        item = content[0]
        text = getattr(item, "text", None)
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return [_single_content_to_value(item) for item in content]


def _content_to_text(content: Any) -> str:
    value = _content_to_value(content)
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def _single_content_to_value(item: Any) -> Any:
    text = getattr(item, "text", None)
    if isinstance(text, str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return item.model_dump(mode="json") if hasattr(item, "model_dump") else str(item)
```

- [ ] **Step 5: Run the session test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_stdio_session.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```powershell
git add app\mcp\mock_server.py app\mcp\stdio_session.py tests\mcp\test_stdio_session.py
git commit -m "feat: add stdio MCP session wrapper"
```

### Task 2: Upgrade MCPClientManager From Process Holder To Session Manager

**Files:**

- Modify: `app/mcp/client_manager.py`
- Test: `tests/mcp/test_client_manager.py`

- [ ] **Step 1: Add failing tests for tool discovery and duplicate startup**

Append to `tests/mcp/test_client_manager.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_client_manager.py -q
```

Expected: fails because `list_tools()` does not exist and duplicate startup raises.

- [ ] **Step 3: Replace `app/mcp/client_manager.py`**

```python
from __future__ import annotations

import asyncio
import threading
from typing import Any

from app.mcp.schemas import MCPServerConfig
from app.mcp.stdio_session import StdioMCPSession


class MCPManagedServer:
    def __init__(self, config: MCPServerConfig, session: StdioMCPSession) -> None:
        self.config = config
        self.session = session

    def is_running(self) -> bool:
        return self.session.is_started


class MCPClientManager:
    def __init__(self) -> None:
        self._servers: dict[str, MCPManagedServer] = {}
        self._lock = threading.Lock()

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
        _run_async(session.start())
        server = MCPManagedServer(config=config, session=session)

        with self._lock:
            self._servers[config.name] = server
        return server

    def stop_server(self, name: str) -> None:
        with self._lock:
            server = self._servers.pop(name, None)
        if server is None:
            raise ValueError(f"Server {name} not found")
        _run_async(server.session.stop())

    def shutdown_all(self) -> None:
        with self._lock:
            servers = list(self._servers.values())
            self._servers.clear()
        for server in servers:
            _run_async(server.session.stop())

    def list_tools(self, server_name: str) -> list[str]:
        server = self._require_server(server_name)
        return _run_async(server.session.list_tools())

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        server = self._require_server(server_name)
        return _run_async(
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


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Synchronous MCPClientManager cannot be used inside a running event loop")
```

- [ ] **Step 4: Update older process-only tests**

Replace `tests/mcp/test_client_manager.py` with:

```python
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig


def test_manager_init():
    manager = MCPClientManager()
    assert manager.list_servers() == []


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
    assert manager.list_servers() == []


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
```

- [ ] **Step 5: Run tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_client_manager.py tests\mcp\test_stdio_session.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add app\mcp\client_manager.py tests\mcp\test_client_manager.py
git commit -m "feat: manage live MCP sessions"
```

### Task 3: Implement MCPToolProxy

**Files:**

- Modify: `app/mcp/tool_proxy.py`
- Test: `tests/mcp/test_tool_proxy.py`

- [ ] **Step 1: Replace proxy tests with behavior tests**

Replace `tests/mcp/test_tool_proxy.py` with:

```python
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_tool_proxy.py -q
```

Expected: fails because `call_tool()` raises `NotImplementedError`.

- [ ] **Step 3: Replace `app/mcp/tool_proxy.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPToolCall, MCPToolResult


class MCPToolProxy:
    def __init__(self, client_manager: MCPClientManager):
        self._manager = client_manager

    def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        started = datetime.now(timezone.utc)
        try:
            result = self._manager.call_tool(
                call.server_name,
                call.tool_name,
                call.arguments,
                timeout_seconds=settings.mcp_tool_timeout,
            )
        except TimeoutError as exc:
            return MCPToolResult(
                status="timeout",
                result=None,
                error=str(exc),
                duration_ms=_duration_ms(started),
                server_name=call.server_name,
                tool_name=call.tool_name,
            )
        except Exception as exc:
            return MCPToolResult(
                status="error",
                result=None,
                error=str(exc),
                duration_ms=_duration_ms(started),
                server_name=call.server_name,
                tool_name=call.tool_name,
            )
        return MCPToolResult(
            status="success",
            result=result,
            error=None,
            duration_ms=_duration_ms(started),
            server_name=call.server_name,
            tool_name=call.tool_name,
        )

    def list_available_tools(self) -> dict[str, list[str]]:
        tools: dict[str, list[str]] = {}
        for server_name in self._manager.list_servers():
            tools[server_name] = self._manager.list_tools(server_name)
        return tools


def _duration_ms(started: datetime) -> float:
    return (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
```

- [ ] **Step 4: Run proxy tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_tool_proxy.py tests\mcp\test_client_manager.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add app\mcp\tool_proxy.py tests\mcp\test_tool_proxy.py
git commit -m "feat: call tools through MCP proxy"
```

---

## Phase 2: Zotero MCP Primary Path With Local HTTP Fallback

### Task 4: Fix Zotero MCP Command Resolution

**Files:**

- Modify: `app/mcp/installer.py`
- Modify: `app/research_workflow/service.py`
- Test: `tests/mcp/test_installer.py`

- [ ] **Step 1: Replace installer tests**

Replace `tests/mcp/test_installer.py` with:

```python
from app.mcp.installer import (
    build_zotero_mcp_command,
    check_zotero_mcp_installed,
)


def test_build_zotero_mcp_command_uses_configured_executable():
    command = build_zotero_mcp_command(
        "D:/Hcworkspace/Anoconda3/envs/research_agent/Scripts/zotero-mcp.exe"
    )
    assert command == [
        "D:/Hcworkspace/Anoconda3/envs/research_agent/Scripts/zotero-mcp.exe"
    ]


def test_build_zotero_mcp_command_falls_back_to_path():
    assert build_zotero_mcp_command("") == ["zotero-mcp"]


def test_check_zotero_mcp_installed_returns_bool():
    assert isinstance(check_zotero_mcp_installed(), bool)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_installer.py -q
```

Expected: fails because `build_zotero_mcp_command` does not exist.

- [ ] **Step 3: Replace `app/mcp/installer.py`**

```python
from __future__ import annotations

import logging
import shlex
import subprocess

logger = logging.getLogger(__name__)


def build_zotero_mcp_command(configured_command: str) -> list[str]:
    configured = configured_command.strip()
    if configured:
        return shlex.split(configured, posix=False)
    return ["zotero-mcp"]


def check_zotero_mcp_installed(command: str = "") -> bool:
    resolved = build_zotero_mcp_command(command)
    probe = [*resolved, "version"]
    try:
        result = subprocess.run(
            probe,
            capture_output=True,
            timeout=10,
            text=True,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def ensure_zotero_mcp_installed(command: str = "") -> tuple[bool, str]:
    if check_zotero_mcp_installed(command):
        return True, ""
    return (
        False,
        "zotero-mcp is not available. Set ZOTERO_MCP_COMMAND to the zotero-mcp executable or install the editable third_party/zotero-mcp package.",
    )
```

- [ ] **Step 4: Update `ResearchRunService._init_mcp_manager()`**

In `app/research_workflow/service.py`, change the imports:

```python
from app.mcp.installer import build_zotero_mcp_command, ensure_zotero_mcp_installed
```

Then replace the Zotero MCP config block inside `_init_mcp_manager()` with:

```python
            try:
                command = build_zotero_mcp_command(settings.zotero_mcp_command)
                config = MCPServerConfig(
                    name="zotero",
                    command=command,
                    env={
                        "ZOTERO_LOCAL": "true" if settings.zotero_local else "false",
                        "ZOTERO_LIBRARY_ID": settings.zotero_library_id,
                        "ZOTERO_LIBRARY_TYPE": settings.zotero_library_type,
                        **({"ZOTERO_DATA_DIR": settings.zotero_data_dir} if settings.zotero_data_dir else {}),
                    },
                )
                manager.start_server(config)
                logger.info("Zotero MCP server started")
            except Exception as e:
                logger.warning(f"Failed to start Zotero MCP server: {e}")
```

Also change:

```python
                success, error = ensure_zotero_mcp_installed()
```

to:

```python
                success, error = ensure_zotero_mcp_installed(settings.zotero_mcp_command)
```

- [ ] **Step 5: Run installer and service smoke tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_installer.py tests\test_research_run_service.py -q
```

Expected: tests pass.

- [ ] **Step 6: Commit**

```powershell
git add app\mcp\installer.py app\research_workflow\service.py tests\mcp\test_installer.py
git commit -m "fix: resolve configured Zotero MCP command"
```

### Task 5: Implement ZoteroMCPAdapter

**Files:**

- Modify: `app/research_workflow/zotero_mcp_adapter.py`
- Test: `tests/research_workflow/test_zotero_mcp_adapter.py`

- [ ] **Step 1: Replace adapter tests with parser and proxy tests**

Replace `tests/research_workflow/test_zotero_mcp_adapter.py` with:

```python
from app.mcp.schemas import MCPToolResult
from app.research_workflow.zotero_mcp_adapter import ZoteroMCPAdapter


class FakeProxy:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def call_tool(self, call):
        self.calls.append(call)
        return self.result


def test_zotero_mcp_adapter_calls_collection_tool():
    proxy = FakeProxy(
        MCPToolResult(
            status="success",
            result=[
                {
                    "key": "ABCD1234",
                    "title": "Demo Paper",
                    "creators": ["Ada Lovelace"],
                    "year": 2026,
                    "doi": "10.1234/demo",
                    "url": "https://example.test/demo",
                    "attachments": [
                        {
                            "key": "PDF12345",
                            "title": "PDF",
                            "path": "D:/papers/demo.pdf",
                            "content_type": "application/pdf",
                        }
                    ],
                }
            ],
            duration_ms=10.0,
            server_name="zotero",
            tool_name="zotero_get_collection_items",
        )
    )

    adapter = ZoteroMCPAdapter(proxy)
    items = adapter.list_collection_items("COLL123")

    assert proxy.calls[0].server_name == "zotero"
    assert proxy.calls[0].tool_name == "zotero_get_collection_items"
    assert proxy.calls[0].arguments == {"collection_key": "COLL123", "detail": "full"}
    assert items[0].key == "ABCD1234"
    assert items[0].title == "Demo Paper"
    assert items[0].attachments[0].path == "D:/papers/demo.pdf"


def test_zotero_mcp_adapter_raises_on_tool_error():
    proxy = FakeProxy(
        MCPToolResult(
            status="error",
            error="zotero unavailable",
            duration_ms=10.0,
            server_name="zotero",
            tool_name="zotero_get_collection_items",
        )
    )

    adapter = ZoteroMCPAdapter(proxy)

    try:
        adapter.list_collection_items("COLL123")
    except RuntimeError as exc:
        assert "zotero unavailable" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\research_workflow\test_zotero_mcp_adapter.py -q
```

Expected: fails because adapter still returns `[]`.

- [ ] **Step 3: Replace `app/research_workflow/zotero_mcp_adapter.py`**

```python
from __future__ import annotations

from typing import Any

from app.mcp.schemas import MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.zotero_intake import (
    ZoteroAttachment,
    ZoteroCollectionItem,
)


class ZoteroMCPAdapter:
    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "zotero"

    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self._server_name,
                tool_name="zotero_get_collection_items",
                arguments={"collection_key": collection_id, "detail": "full"},
            )
        )
        if result.status != "success":
            raise RuntimeError(result.error or "Zotero MCP collection intake failed")
        return [_item_from_mcp_payload(item) for item in _normalize_mcp_items(result.result)]


def _normalize_mcp_items(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    if isinstance(payload, str):
        return []
    return []


def _item_from_mcp_payload(raw: dict[str, Any]) -> ZoteroCollectionItem:
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    return ZoteroCollectionItem(
        key=str(raw.get("key") or data.get("key") or ""),
        title=str(data.get("title") or raw.get("title") or "Untitled Zotero item"),
        creators=_creators_from_payload(data),
        year=_year_from_payload(data),
        doi=data.get("DOI") or data.get("doi"),
        url=data.get("url"),
        attachments=_attachments_from_payload(raw),
        raw=raw,
    )


def _attachments_from_payload(raw: dict[str, Any]) -> list[ZoteroAttachment]:
    attachments = raw.get("attachments") or (raw.get("data") or {}).get("attachments") or []
    parsed: list[ZoteroAttachment] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        data = attachment.get("data") if isinstance(attachment.get("data"), dict) else attachment
        parsed.append(
            ZoteroAttachment(
                key=str(attachment.get("key") or data.get("key") or ""),
                title=str(data.get("title") or ""),
                path=data.get("path") or data.get("localPath") or data.get("href"),
                content_type=data.get("content_type") or data.get("contentType"),
                raw=attachment,
            )
        )
    return parsed


def _creators_from_payload(data: dict[str, Any]) -> list[str]:
    creators = data.get("creators") or []
    if all(isinstance(item, str) for item in creators):
        return list(creators)
    names: list[str] = []
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        if creator.get("name"):
            names.append(str(creator["name"]))
            continue
        name = " ".join(
            str(part)
            for part in (creator.get("firstName"), creator.get("lastName"))
            if part
        ).strip()
        if name:
            names.append(name)
    return names


def _year_from_payload(data: dict[str, Any]) -> int | None:
    if isinstance(data.get("year"), int):
        return data["year"]
    date = str(data.get("date") or "")
    for token in date.replace("-", " ").split():
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None
```

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\research_workflow\test_zotero_mcp_adapter.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add app\research_workflow\zotero_mcp_adapter.py tests\research_workflow\test_zotero_mcp_adapter.py
git commit -m "feat: map Zotero MCP collection items"
```

### Task 6: Wire MCP-First Zotero Intake Into ResearchRunService

**Files:**

- Modify: `app/research_workflow/service.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Add fallback test**

Append to `tests/test_research_run_service.py`:

```python
def test_research_run_service_uses_http_fallback_when_zotero_mcp_unavailable(tmp_path, monkeypatch):
    from app.research_workflow.zotero_intake import ZoteroCollectionItem

    class FakeMCPManager:
        def list_servers(self):
            return ["zotero"]

    class FakeMCPAdapter:
        def __init__(self, _proxy):
            pass

        def list_collection_items(self, _collection_id):
            raise RuntimeError("mcp down")

    class FakeHttpClient:
        def list_collection_items(self, _collection_id):
            return [
                ZoteroCollectionItem(
                    key="ABCD1234",
                    title="Fallback Paper",
                    attachments=[],
                )
            ]

    monkeypatch.setattr("app.research_workflow.service.ZoteroMCPAdapter", FakeMCPAdapter)
    monkeypatch.setattr("app.research_workflow.service.ZoteroLocalHttpClient", FakeHttpClient)

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(
        store=store,
        vault_root=tmp_path / "vault",
        mcp_manager=FakeMCPManager(),
    )
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="Demo")
    )

    executed = service.execute_local_run(run.run_id)

    assert executed.status == "completed"
    assert executed.paper_items[0].title == "Fallback Paper"
    records = (Path(executed.output_dir) / "assets" / "tool-calls.jsonl").read_text(encoding="utf-8")
    assert '"provider": "local_http"' in records
    assert '"fallback_used": true' in records
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_run_service.py::test_research_run_service_uses_http_fallback_when_zotero_mcp_unavailable -q
```

Expected: fails because `ZoteroMCPAdapter` is not imported and service does not attempt MCP first.

- [ ] **Step 3: Update service imports**

Add to `app/research_workflow/service.py` imports:

```python
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.zotero_mcp_adapter import ZoteroMCPAdapter
```

- [ ] **Step 4: Add client factory method to `ResearchRunService`**

Inside `ResearchRunService`, add:

```python
    def _create_zotero_intake_service(self) -> tuple[CollectionIntakeService, str, bool]:
        if self._mcp_manager is not None and "zotero" in self._mcp_manager.list_servers():
            try:
                proxy = MCPToolProxy(self._mcp_manager)
                adapter = ZoteroMCPAdapter(proxy)
                adapter.list_collection_items("__health_check_empty_collection__")
                return CollectionIntakeService(adapter), "zotero_mcp", False
            except Exception as exc:
                logger.warning(f"Zotero MCP unavailable, falling back to local HTTP: {exc}")
        return CollectionIntakeService(ZoteroLocalHttpClient()), "local_http", True
```

Then replace:

```python
            intake_service = intake_service or CollectionIntakeService(
                ZoteroLocalHttpClient()
            )
```

with:

```python
            fallback_provider = "custom"
            fallback_active = False
            if intake_service is None:
                intake_service, fallback_provider, fallback_active = self._create_zotero_intake_service()
```

Then replace the call to `_register_intake_tool`:

```python
        self._register_intake_tool(tool_registry, intake_service)
```

with:

```python
        self._register_intake_tool(
            tool_registry,
            intake_service,
            provider=fallback_provider,
            fallback_active=fallback_active,
        )
```

Change `_register_intake_tool` signature and provider fields:

```python
    def _register_intake_tool(
        self,
        registry: ToolRegistry,
        intake_service: CollectionIntakeService,
        provider: str = "local_http",
        fallback_active: bool = True,
    ) -> None:
        registry.register(
            ToolDefinition(
                name="zotero.list_collection_items",
                provider=provider,
                handler=lambda arguments: intake_service.collect_items(
                    str(arguments["collection_id"]),
                    int(arguments["max_papers"]),
                ),
                required_args=("collection_id", "max_papers"),
                fallback_available=True,
                fallback_active=fallback_active,
            )
        )
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_run_service.py::test_research_run_service_uses_http_fallback_when_zotero_mcp_unavailable tests\test_research_run_service.py::test_research_run_service_execute_local_run_persists_tool_records -q
```

Expected: tests pass.

- [ ] **Step 6: Commit**

```powershell
git add app\research_workflow\service.py tests\test_research_run_service.py
git commit -m "feat: prefer Zotero MCP with HTTP fallback"
```

---

## Phase 3: Minimal External MCP Servers For Semantic Scholar And arXiv

### Task 7: Add Minimal Semantic Scholar MCP Server

**Files:**

- Create: `app/mcp/minimal_semantic_scholar_server.py`
- Modify: `app/research_workflow/semantic_scholar_mcp_adapter.py`
- Test: `tests/mcp/test_minimal_semantic_scholar_server.py`

- [ ] **Step 1: Write server test**

Create `tests/mcp/test_minimal_semantic_scholar_server.py`:

```python
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


def test_semantic_scholar_mcp_server_exposes_search_tool():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="semantic-scholar",
            command=["python", "-m", "app.mcp.minimal_semantic_scholar_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "semantic_scholar_search" in tools["semantic-scholar"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_minimal_semantic_scholar_server.py -q
```

Expected: fails because server module does not exist.

- [ ] **Step 3: Create Semantic Scholar server**

Create `app/mcp/minimal_semantic_scholar_server.py`:

```python
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Semantic Scholar")


@mcp.tool(name="semantic_scholar_search")
def semantic_scholar_search(query: str, limit: int = 5) -> dict[str, Any]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max(1, min(int(limit), 20)),
        "fields": "paperId,title,abstract,year,citationCount,referenceCount,url,authors",
    }
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {
            "query": query,
            "papers": [],
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "query": query,
        "papers": data.get("data", []),
        "fallback_used": False,
    }


@mcp.tool(name="semantic_scholar_get_paper")
def semantic_scholar_get_paper(paper_id: str) -> dict[str, Any]:
    safe_id = quote(paper_id, safe="")
    url = f"https://api.semanticscholar.org/graph/v1/paper/{safe_id}"
    params = {
        "fields": "paperId,title,abstract,year,citationCount,referenceCount,url,authors,references,citations",
    }
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        paper = response.json()
    except Exception as exc:
        return {
            "paper_id": paper_id,
            "paper": None,
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "paper_id": paper_id,
        "paper": paper,
        "fallback_used": False,
    }


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Replace Semantic Scholar adapter**

Replace `app/research_workflow/semantic_scholar_mcp_adapter.py` with:

```python
from __future__ import annotations

from app.mcp.schemas import MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


class SemanticScholarMCPAdapter:
    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "semantic-scholar"

    def search_papers(self, query: str, limit: int = 10) -> list[dict]:
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self._server_name,
                tool_name="semantic_scholar_search",
                arguments={"query": query, "limit": limit},
            )
        )
        if result.status != "success":
            return []
        payload = result.result if isinstance(result.result, dict) else {}
        papers = payload.get("papers", [])
        return papers if isinstance(papers, list) else []
```

- [ ] **Step 5: Run server test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_minimal_semantic_scholar_server.py -q
```

Expected: test passes.

- [ ] **Step 6: Commit**

```powershell
git add app\mcp\minimal_semantic_scholar_server.py app\research_workflow\semantic_scholar_mcp_adapter.py tests\mcp\test_minimal_semantic_scholar_server.py
git commit -m "feat: add Semantic Scholar MCP server"
```

### Task 8: Add Minimal arXiv MCP Server

**Files:**

- Create: `app/mcp/minimal_arxiv_server.py`
- Modify: `app/research_workflow/arxiv_mcp_adapter.py`
- Test: `tests/mcp/test_minimal_arxiv_server.py`

- [ ] **Step 1: Write server test**

Create `tests/mcp/test_minimal_arxiv_server.py`:

```python
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig
from app.mcp.tool_proxy import MCPToolProxy


def test_arxiv_mcp_server_exposes_search_tool():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="arxiv",
            command=["python", "-m", "app.mcp.minimal_arxiv_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "arxiv_search" in tools["arxiv"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_minimal_arxiv_server.py -q
```

Expected: fails because server module does not exist.

- [ ] **Step 3: Create arXiv server**

Create `app/mcp/minimal_arxiv_server.py`:

```python
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("arXiv")

ATOM = "{http://www.w3.org/2005/Atom}"


@mcp.tool(name="arxiv_search")
def arxiv_search(query: str, max_results: int = 5) -> dict[str, Any]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max(1, min(int(max_results), 20)),
    }
    try:
        response = httpx.get("https://export.arxiv.org/api/query", params=params, timeout=10.0)
        response.raise_for_status()
        papers = _parse_arxiv_feed(response.text)
    except Exception as exc:
        return {
            "query": query,
            "papers": [],
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "query": query,
        "papers": papers,
        "fallback_used": False,
    }


def _parse_arxiv_feed(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    papers: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        links = []
        for link in entry.findall(f"{ATOM}link"):
            links.append(link.attrib)
        pdf_url = next(
            (
                link.get("href")
                for link in links
                if link.get("title") == "pdf" or link.get("type") == "application/pdf"
            ),
            None,
        )
        papers.append(
            {
                "id": _text(entry, "id"),
                "title": _clean(_text(entry, "title")),
                "abstract": _clean(_text(entry, "summary")),
                "authors": [_text(author, "name") for author in entry.findall(f"{ATOM}author")],
                "published": _text(entry, "published"),
                "updated": _text(entry, "updated"),
                "url": _text(entry, "id"),
                "pdf_url": pdf_url,
            }
        )
    return papers


def _text(element: ET.Element, name: str) -> str:
    child = element.find(f"{ATOM}{name}")
    return child.text.strip() if child is not None and child.text else ""


def _clean(value: str) -> str:
    return " ".join(value.split())


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Replace arXiv adapter**

Replace `app/research_workflow/arxiv_mcp_adapter.py` with:

```python
from __future__ import annotations

from app.mcp.schemas import MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


class ArxivMCPAdapter:
    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "arxiv"

    def search_papers(self, query: str, max_results: int = 10) -> list[dict]:
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self._server_name,
                tool_name="arxiv_search",
                arguments={"query": query, "max_results": max_results},
            )
        )
        if result.status != "success":
            return []
        payload = result.result if isinstance(result.result, dict) else {}
        papers = payload.get("papers", [])
        return papers if isinstance(papers, list) else []
```

- [ ] **Step 5: Run server test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_minimal_arxiv_server.py -q
```

Expected: test passes.

- [ ] **Step 6: Commit**

```powershell
git add app\mcp\minimal_arxiv_server.py app\research_workflow\arxiv_mcp_adapter.py tests\mcp\test_minimal_arxiv_server.py
git commit -m "feat: add arXiv MCP server"
```

### Task 9: Start Optional Semantic Scholar And arXiv MCP Servers

**Files:**

- Modify: `app/config.py`
- Modify: `.env.example`
- Modify: `app/research_workflow/service.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Add config test**

Append to `tests/test_research_run_service.py`:

```python
def test_research_run_service_can_start_optional_mcp_servers(tmp_path, monkeypatch):
    started = []

    class FakeManager:
        def start_server(self, config):
            started.append((config.name, config.command))

        def list_servers(self):
            return [name for name, _command in started]

    monkeypatch.setattr("app.research_workflow.service.MCPClientManager", FakeManager)
    monkeypatch.setattr("app.research_workflow.service.ensure_zotero_mcp_installed", lambda _command="": (False, "disabled"))
    monkeypatch.setattr("app.research_workflow.service.settings.mcp_enabled", True)
    monkeypatch.setattr("app.research_workflow.service.settings.zotero_mcp_enabled", False)
    monkeypatch.setattr("app.research_workflow.service.settings.semantic_scholar_mcp_enabled", True)
    monkeypatch.setattr("app.research_workflow.service.settings.arxiv_mcp_enabled", True)

    ResearchRunService(store=FileResearchRunStore(tmp_path / "runs.json"), vault_root=tmp_path)

    assert ("semantic-scholar", ["python", "-m", "app.mcp.minimal_semantic_scholar_server"]) in started
    assert ("arxiv", ["python", "-m", "app.mcp.minimal_arxiv_server"]) in started
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_run_service.py::test_research_run_service_can_start_optional_mcp_servers -q
```

Expected: fails because settings are missing.

- [ ] **Step 3: Add settings**

In `app/config.py`, add under MCP settings:

```python
    semantic_scholar_mcp_enabled: bool = False
    arxiv_mcp_enabled: bool = False
    research_agent_mcp_enabled: bool = True
```

In `.env.example`, add:

```text
SEMANTIC_SCHOLAR_MCP_ENABLED=false
ARXIV_MCP_ENABLED=false
RESEARCH_AGENT_MCP_ENABLED=true
```

- [ ] **Step 4: Start optional servers in `_init_mcp_manager()`**

In `app/research_workflow/service.py`, after Zotero startup block, add:

```python
        if settings.semantic_scholar_mcp_enabled:
            try:
                manager.start_server(
                    MCPServerConfig(
                        name="semantic-scholar",
                        command=["python", "-m", "app.mcp.minimal_semantic_scholar_server"],
                    )
                )
                logger.info("Semantic Scholar MCP server started")
            except Exception as e:
                logger.warning(f"Failed to start Semantic Scholar MCP server: {e}")

        if settings.arxiv_mcp_enabled:
            try:
                manager.start_server(
                    MCPServerConfig(
                        name="arxiv",
                        command=["python", "-m", "app.mcp.minimal_arxiv_server"],
                    )
                )
                logger.info("arXiv MCP server started")
            except Exception as e:
                logger.warning(f"Failed to start arXiv MCP server: {e}")
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_run_service.py::test_research_run_service_can_start_optional_mcp_servers -q
```

Expected: test passes.

- [ ] **Step 6: Commit**

```powershell
git add app\config.py .env.example app\research_workflow\service.py tests\test_research_run_service.py
git commit -m "feat: configure optional research MCP servers"
```

---

## Phase 4: ResearchAgent As A Standard MCP Server

### Task 10: Add ResearchAgent MCP Stdio Server

**Files:**

- Create: `app/research_workflow/mcp_stdio_server.py`
- Test: `tests/mcp/test_research_agent_mcp_stdio_server.py`

- [ ] **Step 1: Write stdio server test**

Create `tests/mcp/test_research_agent_mcp_stdio_server.py`:

```python
from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


def test_research_agent_mcp_stdio_server_lists_tools():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="research-agent",
            command=["python", "-m", "app.research_workflow.mcp_stdio_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "research_agent_list_runs" in tools["research-agent"]
    assert "research_agent_export_knowledge_pack" in tools["research-agent"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_research_agent_mcp_stdio_server.py -q
```

Expected: fails because server module does not exist.

- [ ] **Step 3: Create server module**

Create `app/research_workflow/mcp_stdio_server.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.config import settings
from app.research_workflow.mcp_server import MCPToolRequest, ResearchAgentMCPServer
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore

mcp = FastMCP("ResearchAgent")


def _server() -> ResearchAgentMCPServer:
    store_path = Path(settings.storage_dir) / "research_runs.json"
    service = ResearchRunService(
        store=FileResearchRunStore(store_path),
        vault_root=settings.obsidian_vault_root,
    )
    return ResearchAgentMCPServer(service)


@mcp.tool(name="research_agent_list_runs")
def research_agent_list_runs() -> dict[str, Any]:
    service = _server()._service
    return {"runs": [run.model_dump(mode="json") for run in service.list_runs()]}


@mcp.tool(name="research_agent_list_papers")
def research_agent_list_papers(run_id: str) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.list_papers",
            arguments={"run_id": run_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_get_run_trace")
def research_agent_get_run_trace(run_id: str) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.get_run_trace",
            arguments={"run_id": run_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_export_knowledge_pack")
def research_agent_export_knowledge_pack(run_id: str) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.export_knowledge_pack",
            arguments={"run_id": run_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_search_chunks")
def research_agent_search_chunks(query: str, top_k: int = 5, paper_id: str | None = None) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.search_chunks",
            arguments={"query": query, "top_k": top_k, "paper_id": paper_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_answer_question")
def research_agent_answer_question(question: str, run_id: str | None = None, paper_id: str | None = None, top_k: int = 5) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.answer_question",
            arguments={
                "question": question,
                "run_id": run_id,
                "paper_id": paper_id,
                "top_k": top_k,
            },
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_compare_papers")
def research_agent_compare_papers(paper_ids: list[str]) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.compare_papers",
            arguments={"paper_ids": paper_ids},
        )
    ).model_dump(mode="json")


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run stdio server test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp\test_research_agent_mcp_stdio_server.py -q
```

Expected: test passes.

- [ ] **Step 5: Commit**

```powershell
git add app\research_workflow\mcp_stdio_server.py tests\mcp\test_research_agent_mcp_stdio_server.py
git commit -m "feat: expose ResearchAgent as MCP server"
```

---

## Phase 5: MCP Hub Status UI And Documentation

### Task 11: Report Real MCP Health Through API

**Files:**

- Modify: `app/routers/research_runs.py`
- Test: `tests/test_research_run_router.py`

- [ ] **Step 1: Add API health test**

Append to `tests/test_research_run_router.py`:

```python
def test_tool_health_reports_mcp_state(client):
    response = client.get("/research-runs/tools/health")

    assert response.status_code == 200
    tools = response.json()
    assert any(tool["tool_name"] == "ResearchAgent MCP Server" for tool in tools)
    assert all("provider" in tool for tool in tools)
    assert all("fallback_active" in tool for tool in tools)
```

- [ ] **Step 2: Run test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_run_router.py::test_tool_health_reports_mcp_state -q
```

Expected: either passes already or fails because health route omits fallback fields.

- [ ] **Step 3: Update health payload**

In `app/routers/research_runs.py`, ensure every tool health dict has:

```python
{
    "tool_name": tool_name,
    "provider": provider,
    "available": available,
    "fallback_available": fallback_available,
    "fallback_active": fallback_active,
    "message": message,
}
```

For MCP manager-backed servers, add:

```python
{
    "tool_name": f"{server_name} MCP Server",
    "provider": "mcp",
    "available": True,
    "fallback_available": server_name == "zotero",
    "fallback_active": False,
    "message": f"{len(manager.list_tools(server_name))} MCP tool(s) discovered",
}
```

- [ ] **Step 4: Run router tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_run_router.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add app\routers\research_runs.py tests\test_research_run_router.py
git commit -m "feat: expose MCP hub health"
```

### Task 12: Update Streamlit MCP Hub Panel

**Files:**

- Modify: `ui/streamlit_app.py`
- Test: `tests/test_research_workflow_ui_import.py`

- [ ] **Step 1: Add UI source test**

Append to `tests/test_research_workflow_ui_import.py`:

```python
def test_research_workflow_ui_labels_mcp_fallbacks():
    source = Path("ui/streamlit_app.py").read_text(encoding="utf-8")

    assert "MCP Hub" in source
    assert "fallback_active" in source
    assert "tools discovered" in source or "tool(s) discovered" in source
```

- [ ] **Step 2: Run test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_workflow_ui_import.py::test_research_workflow_ui_labels_mcp_fallbacks -q
```

Expected: fails if UI still uses generic text only.

- [ ] **Step 3: Update the tool health panel**

In `ui/streamlit_app.py`, replace the tool health caption block with:

```python
    st.subheader("MCP Hub")
    for tool in get_tool_health_status():
        tool_name = tool.get("tool_name", "unknown")
        provider = tool.get("provider", "unknown")
        available = bool(tool.get("available"))
        fallback_active = bool(tool.get("fallback_active"))
        fallback_available = bool(tool.get("fallback_available"))
        message = tool.get("message", "")
        state = "available" if available else "unavailable"
        if fallback_active:
            state = "fallback active"
        fallback = "fallback available" if fallback_available else "no fallback"
        st.caption(f"{tool_name} ({provider}): {state}, {fallback}. {message}")
    st.caption("MCP Hub shows real server state, tool(s) discovered, and fallback activity.")
```

- [ ] **Step 4: Run UI tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\test_research_workflow_ui_import.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add ui\streamlit_app.py tests\test_research_workflow_ui_import.py
git commit -m "feat: show MCP hub status in UI"
```

### Task 13: Add MCP Hub Runbook

**Files:**

- Modify: `docs/RUN_GUIDE.md`
- Modify: `docs/JD_MCP_CAPABILITIES.md`

- [ ] **Step 1: Add runbook section to `docs/RUN_GUIDE.md`**

Append:

```markdown
## MCP Hub Demo Verification

Run all commands from `E:\projects\ResearchAgent`.

1. Verify Zotero local API:

```powershell
cmd /c "netstat -ano -p tcp | findstr :23119"
curl.exe -v "http://127.0.0.1:23119/api/users/0/items?limit=1"
```

Expected:

- `23119` is listening on `127.0.0.1`.
- `curl` returns `HTTP/1.0 200 OK`.

2. Verify Zotero MCP executable:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\Scripts\zotero-mcp.exe" version
```

Expected: prints `Zotero MCP v0.4.1` or a newer installed version.

3. Run MCP tests:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp tests\research_workflow\test_zotero_mcp_adapter.py tests\test_research_agent_mcp_server.py tests\test_research_run_router.py -q
```

Expected: all selected tests pass.

4. Start the API:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected: `GET http://127.0.0.1:8000/health` returns `200 OK`.

5. Start Streamlit:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m streamlit run ui/streamlit_app.py
```

Expected: the Research Workflow page shows MCP Hub status for Zotero, ResearchAgent, Semantic Scholar, arXiv, and Obsidian.
```

- [ ] **Step 2: Update capability wording**

In `docs/JD_MCP_CAPABILITIES.md`, ensure it distinguishes:

```markdown
- Implemented: local Zotero API fallback, Research Run workflow, Knowledge Pack generation, FastAPI tool facade.
- Implemented after MCP Hub completion: standard MCP client calls, Zotero MCP primary intake, Semantic Scholar MCP, arXiv MCP, ResearchAgent stdio MCP server.
- Not claimed: production hosted MCP gateway, multi-user auth, cloud deployment.
```

- [ ] **Step 3: Commit**

```powershell
git add docs\RUN_GUIDE.md docs\JD_MCP_CAPABILITIES.md
git commit -m "docs: add MCP hub runbook"
```

---

## Phase 6: End-To-End Verification

### Task 14: Add MCP Hub E2E Test

**Files:**

- Create: `tests/integration/test_mcp_hub_e2e.py`

- [ ] **Step 1: Create test**

Create `tests/integration/test_mcp_hub_e2e.py`:

```python
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
```

- [ ] **Step 2: Run E2E test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\integration\test_mcp_hub_e2e.py -q
```

Expected: test passes without requiring network calls.

- [ ] **Step 3: Run full MCP-related suite**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp tests\integration\test_mcp_hub_e2e.py tests\research_workflow\test_zotero_mcp_adapter.py tests\test_research_agent_mcp_server.py tests\test_research_run_router.py tests\test_research_run_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit**

```powershell
git add tests\integration\test_mcp_hub_e2e.py
git commit -m "test: cover MCP hub end to end"
```

### Task 15: Manual Demo Gate

**Files:**

- No code changes.

- [ ] **Step 1: Verify Zotero local API**

Run:

```powershell
cmd /c "netstat -ano -p tcp | findstr :23119"
curl.exe -v "http://127.0.0.1:23119/api/users/0/items?limit=1"
```

Expected:

- `netstat` shows `127.0.0.1:23119 LISTENING`.
- `curl` shows `HTTP/1.0 200 OK`.

- [ ] **Step 2: Verify Zotero MCP CLI**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\Scripts\zotero-mcp.exe" version
```

Expected: a Zotero MCP version string.

- [ ] **Step 3: Run collection CLI smoke test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\Scripts\zotero-cli.exe" get collections --limit 3
```

Expected: prints the user's Zotero collections.

- [ ] **Step 4: Start app services**

In one terminal:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m streamlit run ui/streamlit_app.py
```

Expected:

- API starts without MCP startup errors.
- Streamlit starts and the Research Workflow page is reachable.

- [ ] **Step 5: Run flagship workflow**

Use the Streamlit Research Workflow page:

- Select Zotero collection key `WY47EPBS` or another known collection.
- Set `max_papers` to `2`.
- Enable Semantic Scholar and arXiv only if network is available.
- Leave Obsidian publishing disabled for the first run.
- Execute the local run.

Expected:

- Run status becomes `completed`.
- The Knowledge Pack output directory exists.
- `assets/tool-calls.jsonl` records Zotero provider and fallback state.
- The UI shows MCP Hub status honestly.

---

## Completion Checklist

- [ ] `MCPToolProxy.call_tool()` no longer raises `NotImplementedError`.
- [ ] `MCPClientManager` can list and call tools from a stdio MCP server.
- [ ] Zotero MCP command uses `ZOTERO_MCP_COMMAND` before `PATH`.
- [ ] Zotero collection intake prefers MCP and falls back to local HTTP.
- [ ] Semantic Scholar MCP server exposes `semantic_scholar_search`.
- [ ] arXiv MCP server exposes `arxiv_search`.
- [ ] ResearchAgent stdio MCP server exposes its own tools.
- [ ] UI distinguishes MCP available, unavailable, and fallback active.
- [ ] `tool-calls.jsonl` records provider and fallback state.
- [ ] The MCP Hub runbook exists in `docs/RUN_GUIDE.md`.
- [ ] The selected MCP-related test suite passes.
- [ ] Manual Zotero API and `zotero-cli` smoke tests pass.

---

## Self-Review Notes

Spec coverage:

- Standard MCP client: Tasks 1-3.
- Zotero MCP primary path: Tasks 4-6.
- Semantic Scholar and arXiv MCP: Tasks 7-9.
- ResearchAgent MCP server: Task 10.
- MCP health UI and docs: Tasks 11-13.
- E2E and manual verification: Tasks 14-15.

Placeholder scan:

- This plan intentionally avoids unresolved placeholder markers, open-ended test instructions, and undefined implementation steps.
- Where future behavior depends on network availability, the plan specifies fallback output and non-network tests.

Type consistency:

- `MCPServerConfig`, `MCPToolCall`, and `MCPToolResult` match current `app/mcp/schemas.py`.
- `ZoteroCollectionItem` and `ZoteroAttachment` match current `app/research_workflow/zotero_intake.py`.
- `ResearchAgentMCPServer` remains the shared facade for FastAPI and stdio MCP.
