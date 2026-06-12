from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings
from app.research_workflow.tool_adapters import (
    ArxivAdapter,
    ObsidianAdapter,
    SemanticScholarAdapter,
)
from app.research_workflow.tool_registry import ToolHealth, build_default_tool_registry


def build_mcp_hub_health(
    service: Any | None = None,
    storage_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Build the user-facing MCP Hub status payload."""
    root = Path(storage_root) if storage_root is not None else Path(settings.metadata_dir).parent
    manager = getattr(service, "_mcp_manager", None)
    running_servers = _running_servers(manager)

    tools = [
        _normalize_health(health.model_dump(mode="json"))
        for health in build_default_tool_registry().health()
    ]
    tools.extend(
        _normalize_health(health.model_dump(mode="json"))
        for health in (
            ObsidianAdapter(root / "knowledge_packs").health(),
            SemanticScholarAdapter(available="semantic-scholar" in running_servers).health(),
            ArxivAdapter(available="arxiv" in running_servers).health(),
        )
    )

    tools.append(_server_health(manager, "zotero", "Zotero MCP Server"))
    tools.append(
        _server_health(
            manager,
            "semantic-scholar",
            "Semantic Scholar MCP Server",
        )
    )
    tools.append(_server_health(manager, "arxiv", "arXiv MCP Server"))
    tools.append(_research_agent_server_health())
    return tools


def _running_servers(manager: Any | None) -> set[str]:
    if manager is None:
        return set()
    try:
        return set(manager.list_servers())
    except Exception:
        return set()


def _server_health(
    manager: Any | None,
    server_name: str,
    label: str,
) -> dict[str, Any]:
    fallback_provider = {
        "zotero": "local_http",
        "semantic-scholar": "local_metadata",
        "arxiv": "local_metadata",
    }.get(server_name, "local")
    fallback_message = {
        "zotero": "MCP server is not running; Zotero local HTTP fallback is active",
        "semantic-scholar": "MCP server is not running; local metadata fallback is active",
        "arxiv": "MCP server is not running; local paper metadata fallback is active",
    }.get(server_name, "MCP server is not running")

    if manager is not None:
        try:
            if server_name in manager.list_servers():
                tools = manager.list_tools(server_name)
                return _normalize_health(
                    {
                        "tool_name": label,
                        "provider": "mcp",
                        "available": True,
                        "fallback_available": server_name in {"zotero", "semantic-scholar", "arxiv"},
                        "fallback_active": False,
                        "message": f"{len(tools)} MCP tool(s) discovered",
                        "tool_count": len(tools),
                        "state": "running",
                    }
                )
        except Exception as exc:
            return _normalize_health(
                {
                    "tool_name": label,
                    "provider": fallback_provider,
                    "available": False,
                    "fallback_available": True,
                    "fallback_active": True,
                    "message": f"MCP health check failed: {exc}",
                    "tool_count": 0,
                    "state": "fallback_active",
                }
            )

    return _normalize_health(
        {
            "tool_name": label,
            "provider": fallback_provider,
            "available": False,
            "fallback_available": True,
            "fallback_active": True,
            "message": fallback_message,
            "tool_count": 0,
            "state": "fallback_active",
        }
    )


def _research_agent_server_health() -> dict[str, Any]:
    if settings.research_agent_mcp_enabled:
        return _normalize_health(
            {
                "tool_name": "ResearchAgent MCP Server",
                "provider": "mcp_stdio",
                "available": True,
                "fallback_available": False,
                "fallback_active": False,
                "message": "Standard stdio MCP entry point is available",
                "tool_count": 7,
                "state": "available",
            }
        )
    return _normalize_health(
        {
            "tool_name": "ResearchAgent MCP Server",
            "provider": "disabled",
            "available": False,
            "fallback_available": False,
            "fallback_active": False,
            "message": "ResearchAgent MCP stdio server is disabled",
            "tool_count": 0,
            "state": "disabled",
        }
    )


def _normalize_health(payload: ToolHealth | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, ToolHealth):
        data = payload.model_dump(mode="json")
    else:
        data = dict(payload)
    data.setdefault("tool_name", "unknown")
    data.setdefault("provider", "unknown")
    data.setdefault("available", False)
    data.setdefault("fallback_available", False)
    data.setdefault("fallback_active", False)
    data.setdefault("message", "")
    data.setdefault("tool_count", None)
    data.setdefault("state", _state_for(data))
    return data


def _state_for(data: dict[str, Any]) -> str:
    if data.get("fallback_active"):
        return "fallback_active"
    if data.get("available"):
        return "available"
    return "unavailable"
