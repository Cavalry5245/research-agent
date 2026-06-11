from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.research_workflow.knowledge_pack import append_tool_call_record
from app.research_workflow.schemas import ResearchRun


ToolCallStatus = Literal["completed", "failed"]
ToolHandler = Callable[[dict[str, Any]], Any]
ToolHealthCheck = Callable[[], "ToolHealth | Mapping[str, Any] | bool | str"]


class ToolCallResult(BaseModel):
    tool_name: str
    provider: str
    status: ToolCallStatus
    result: Any = None
    result_summary: str = ""
    error: str | None = None
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0.0)
    fallback_used: bool = False

    def to_record(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "provider": self.provider,
            "arguments": dict(arguments),
            "status": self.status,
            "result_summary": self.result_summary,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "fallback_used": self.fallback_used,
        }


class ToolHealth(BaseModel):
    tool_name: str
    provider: str
    available: bool
    fallback_available: bool = False
    fallback_active: bool = False
    message: str = ""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    provider: str
    handler: ToolHandler
    required_args: tuple[str, ...] = field(default_factory=tuple)
    health_check: ToolHealthCheck | None = None
    fallback_available: bool = False
    fallback_active: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._records: list[dict[str, Any]] = []

    def register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition

    def dispatch(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
        run: ResearchRun | None = None,
    ) -> ToolCallResult:
        args = dict(arguments or {})
        definition = self._tools.get(tool_name)
        if definition is None:
            result = self._failed_result(
                tool_name=tool_name,
                provider="unknown",
                error=f"Tool is not registered: {tool_name}",
                fallback_used=False,
            )
            self._record(result, args, run)
            return result

        missing_args = [
            arg_name
            for arg_name in definition.required_args
            if arg_name not in args or args[arg_name] is None
        ]
        if missing_args:
            result = self._failed_result(
                tool_name=definition.name,
                provider=definition.provider,
                error=f"Missing required argument(s): {', '.join(missing_args)}",
                fallback_used=definition.fallback_active,
            )
            self._record(result, args, run)
            return result

        started_at = _utc_now()
        try:
            raw_result = definition.handler(args)
        except Exception as exc:
            result = self._failed_result(
                tool_name=definition.name,
                provider=definition.provider,
                error=str(exc),
                fallback_used=definition.fallback_active,
                started_at=started_at,
            )
            self._record(result, args, run)
            return result

        completed_at = _utc_now()
        result = ToolCallResult(
            tool_name=definition.name,
            provider=definition.provider,
            status="completed",
            result=raw_result,
            result_summary=_summarize_result(raw_result),
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=_duration_ms(started_at, completed_at),
            fallback_used=definition.fallback_active,
        )
        self._record(result, args, run)
        return result

    def health(self) -> list[ToolHealth]:
        return [self._health_for(definition) for definition in self._tools.values()]

    def call_records(self) -> list[dict[str, Any]]:
        return list(self._records)

    def _health_for(self, definition: ToolDefinition) -> ToolHealth:
        if definition.health_check is None:
            return ToolHealth(
                tool_name=definition.name,
                provider=definition.provider,
                available=True,
                fallback_available=definition.fallback_available,
                fallback_active=definition.fallback_active,
                message="registered",
            )

        try:
            raw = definition.health_check()
        except Exception as exc:
            return ToolHealth(
                tool_name=definition.name,
                provider=definition.provider,
                available=False,
                fallback_available=definition.fallback_available,
                fallback_active=definition.fallback_active,
                message=str(exc),
            )

        if isinstance(raw, ToolHealth):
            return raw
        if isinstance(raw, Mapping):
            payload = dict(raw)
            payload.setdefault("tool_name", definition.name)
            payload.setdefault("provider", definition.provider)
            payload.setdefault("fallback_available", definition.fallback_available)
            payload.setdefault("fallback_active", definition.fallback_active)
            return ToolHealth.model_validate(payload)
        if isinstance(raw, bool):
            return ToolHealth(
                tool_name=definition.name,
                provider=definition.provider,
                available=raw,
                fallback_available=definition.fallback_available,
                fallback_active=definition.fallback_active,
                message="available" if raw else "unavailable",
            )
        return ToolHealth(
            tool_name=definition.name,
            provider=definition.provider,
            available=True,
            fallback_available=definition.fallback_available,
            fallback_active=definition.fallback_active,
            message=str(raw),
        )

    def _failed_result(
        self,
        tool_name: str,
        provider: str,
        error: str,
        fallback_used: bool,
        started_at: datetime | None = None,
    ) -> ToolCallResult:
        started = started_at or _utc_now()
        completed = _utc_now()
        return ToolCallResult(
            tool_name=tool_name,
            provider=provider,
            status="failed",
            result=None,
            result_summary=error,
            error=error,
            started_at=started,
            completed_at=completed,
            duration_ms=_duration_ms(started, completed),
            fallback_used=fallback_used,
        )

    def _record(
        self,
        result: ToolCallResult,
        arguments: Mapping[str, Any],
        run: ResearchRun | None,
    ) -> None:
        record = result.to_record(arguments)
        self._records.append(record)
        if run is not None:
            append_tool_call_record(run, record)


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="research_agent.echo",
            provider="local",
            handler=lambda arguments: {"echo": arguments.get("message", "")},
            required_args=("message",),
            fallback_available=True,
            fallback_active=False,
        )
    )
    registry.register(
        ToolDefinition(
            name="zotero.list_collection_items",
            provider="local_http",
            handler=_unconfigured_tool_handler("zotero.list_collection_items"),
            required_args=("collection_id", "max_papers"),
            fallback_available=True,
            fallback_active=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="research_agent.process_paper",
            provider="local_service",
            handler=_unconfigured_tool_handler("research_agent.process_paper"),
            required_args=("zotero_item_id", "run_output_dir"),
        )
    )
    registry.register(
        ToolDefinition(
            name="research_agent.generate_knowledge_pack",
            provider="local_synthesis",
            handler=_unconfigured_tool_handler(
                "research_agent.generate_knowledge_pack"
            ),
            required_args=("run_id",),
        )
    )
    registry.register(
        ToolDefinition(
            name="obsidian.publish_knowledge_pack",
            provider="direct_markdown",
            handler=_unconfigured_tool_handler("obsidian.publish_knowledge_pack"),
            required_args=("run_id", "output_dir"),
            fallback_available=True,
            fallback_active=True,
        )
    )
    return registry


def _unconfigured_tool_handler(tool_name: str) -> ToolHandler:
    def handler(_arguments: dict[str, Any]) -> Any:
        raise RuntimeError(f"{tool_name} requires run-specific dependencies")

    return handler


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _duration_ms(started_at: datetime, completed_at: datetime) -> float:
    return max((completed_at - started_at).total_seconds() * 1000.0, 0.0)


def _summarize_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        for key in ("summary", "message", "path", "status"):
            value = result.get(key)
            if value:
                return str(value)
        return f"{len(result)} field(s)"
    if isinstance(result, list):
        return f"{len(result)} item(s)"
    return str(result)
