from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from concurrent.futures import Future
from contextlib import suppress
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Coroutine, Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp.schemas import MCPServerConfig


class MCPEventLoopThread:
    """Owns a long-lived event loop for stdio MCP sessions."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="researchagent-mcp-loop",
            daemon=True,
        )
        self._thread.start()

    def run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def stop(self) -> None:
        if self._loop.is_closed():
            return
        stopper: Future[None] = asyncio.run_coroutine_threadsafe(
            self._shutdown(),
            self._loop,
        )
        stopper.result()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _shutdown(self) -> None:
        tasks = [
            task
            for task in asyncio.all_tasks(self._loop)
            if task is not asyncio.current_task(self._loop)
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class StdioMCPSession:
    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._queue: asyncio.Queue[_SessionRequest] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._session: ClientSession | None = None

    @property
    def is_started(self) -> bool:
        return self._session is not None and self._worker_task is not None and not self._worker_task.done()

    async def start(self) -> None:
        if self.is_started:
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[_SessionRequest] = asyncio.Queue()
        started: asyncio.Future[None] = loop.create_future()
        worker = asyncio.create_task(
            self._run_session(queue, started),
            name=f"researchagent-mcp-session-{self.config.name}",
        )
        self._queue = queue
        self._worker_task = worker

        try:
            await started
        except Exception:
            with suppress(Exception):
                await worker
            self._queue = None
            self._worker_task = None
            self._session = None
            raise

    async def stop(self) -> None:
        worker = self._worker_task
        queue = self._queue
        if worker is None:
            return

        if not worker.done() and queue is not None:
            stop_future = asyncio.get_running_loop().create_future()
            await queue.put(_SessionRequest(action="stop", future=stop_future))
            await stop_future
        else:
            with suppress(Exception):
                await worker

        self._queue = None
        self._worker_task = None
        self._session = None

    async def list_tools(self) -> list[str]:
        return await self._request(_SessionRequest(action="list_tools"))

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        return await self._request(
            _SessionRequest(
                action="call_tool",
                tool_name=tool_name,
                arguments=arguments or {},
                timeout_seconds=timeout_seconds,
            )
        )

    async def _request(self, request: "_SessionRequest") -> Any:
        queue = self._queue
        if not self.is_started or queue is None:
            raise RuntimeError(f"MCP server is not started: {self.config.name}")
        request.future = asyncio.get_running_loop().create_future()
        await queue.put(request)
        return await request.future

    async def _run_session(
        self,
        queue: "asyncio.Queue[_SessionRequest]",
        started: "asyncio.Future[None]",
    ) -> None:
        stack = AsyncExitStack()
        stop_future: asyncio.Future[None] | None = None
        try:
            params = StdioServerParameters(
                command=_resolve_command(self.config.command[0]),
                args=self.config.command[1:],
                env=_merged_env(self.config.env),
                cwd=self.config.cwd,
            )
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            self._session = session
            if not started.done():
                started.set_result(None)

            while True:
                request = await queue.get()
                if request.action == "stop":
                    stop_future = request.future
                    break
                await self._handle_request(session, request)
        except Exception as exc:
            if not started.done():
                started.set_exception(exc)
            _fail_pending_requests(queue, exc)
            if stop_future is not None and not stop_future.done():
                stop_future.set_exception(exc)
        finally:
            self._session = None
            try:
                await stack.aclose()
            except Exception as exc:
                if not started.done():
                    started.set_exception(exc)
                _fail_pending_requests(queue, exc)
                if stop_future is not None and not stop_future.done():
                    stop_future.set_exception(exc)
            else:
                if stop_future is not None and not stop_future.done():
                    stop_future.set_result(None)

    async def _handle_request(
        self,
        session: ClientSession,
        request: "_SessionRequest",
    ) -> None:
        if request.future is None:
            raise RuntimeError("MCP session request is missing a future")
        try:
            if request.action == "list_tools":
                result = await session.list_tools()
                request.future.set_result([tool.name for tool in result.tools])
                return
            if request.action == "call_tool":
                result = await self._call_session_tool(session, request)
                request.future.set_result(result)
                return
            request.future.set_exception(RuntimeError(f"Unsupported MCP session action: {request.action}"))
        except Exception as exc:
            request.future.set_exception(exc)

    async def _call_session_tool(
        self,
        session: ClientSession,
        request: "_SessionRequest",
    ) -> Any:
        timeout = (
            timedelta(seconds=request.timeout_seconds)
            if request.timeout_seconds is not None
            else None
        )
        result = await session.call_tool(
            request.tool_name or "",
            request.arguments or {},
            read_timeout_seconds=timeout,
        )
        if result.isError:
            text = _content_to_text(result.content)
            raise RuntimeError(text or f"MCP tool failed: {request.tool_name}")
        return _content_to_value(result.content)


@dataclass
class _SessionRequest:
    action: Literal["list_tools", "call_tool", "stop"]
    future: asyncio.Future[Any] | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    timeout_seconds: float | None = None


def _resolve_command(command: str) -> str:
    if command.lower() in {"python", "python.exe"}:
        return sys.executable
    return command


def _merged_env(env: dict[str, str]) -> dict[str, str] | None:
    if not env:
        return None
    merged = dict(os.environ)
    merged.update(env)
    return merged


def _fail_pending_requests(
    queue: "asyncio.Queue[_SessionRequest]",
    exc: Exception,
) -> None:
    while True:
        try:
            request = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        if request.future is not None and not request.future.done():
            request.future.set_exception(exc)


def _content_to_value(content: Any) -> Any:
    if not content:
        return None
    if len(content) == 1:
        return _single_content_to_value(content[0])
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
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return str(item)
