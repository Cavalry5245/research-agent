import json
from datetime import datetime, timezone
from pathlib import Path

from app.research_workflow.knowledge_pack import create_knowledge_pack_skeleton
from app.research_workflow.schemas import ResearchRun, build_default_steps
from app.research_workflow.tool_registry import (
    ToolDefinition,
    ToolHealth,
    ToolRegistry,
    build_default_tool_registry,
)


def test_default_tool_registry_dispatches_echo():
    registry = build_default_tool_registry()

    result = registry.dispatch("research_agent.echo", {"message": "hello"})

    assert result.status == "completed"
    assert result.tool_name == "research_agent.echo"
    assert result.provider == "local"
    assert result.result == {"echo": "hello"}
    assert result.result_summary == "1 field(s)"
    assert result.error is None
    assert result.duration_ms >= 0.0
    assert registry.call_records()[0]["arguments"] == {"message": "hello"}


def test_tool_registry_validates_required_arguments():
    registry = build_default_tool_registry()

    result = registry.dispatch("research_agent.echo", {})

    assert result.status == "failed"
    assert result.provider == "local"
    assert "Missing required argument" in (result.error or "")
    assert result.result_summary == result.error
    assert registry.call_records()[0]["status"] == "failed"


def test_tool_registry_normalizes_missing_tool():
    registry = build_default_tool_registry()

    result = registry.dispatch("missing.tool", {})

    assert result.status == "failed"
    assert result.provider == "unknown"
    assert "not registered" in (result.error or "")


def test_tool_registry_normalizes_handler_exception():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="research_agent.explode",
            provider="local",
            handler=lambda arguments: (_ for _ in ()).throw(RuntimeError("boom")),
        )
    )

    result = registry.dispatch("research_agent.explode", {})

    assert result.status == "failed"
    assert result.provider == "local"
    assert result.error == "boom"
    assert result.result_summary == "boom"


def test_tool_registry_reports_health_and_fallback_fields():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="research_agent.local_only",
            provider="local_fallback",
            handler=lambda arguments: {"ok": True},
            fallback_available=True,
            fallback_active=True,
            health_check=lambda: ToolHealth(
                tool_name="research_agent.local_only",
                provider="local_fallback",
                available=True,
                fallback_available=True,
                fallback_active=True,
                message="using local fallback",
            ),
        )
    )

    result = registry.dispatch("research_agent.local_only", {})
    health = registry.health()[0]

    assert result.fallback_used is True
    assert health.available is True
    assert health.fallback_available is True
    assert health.fallback_active is True
    assert health.message == "using local fallback"


def test_tool_registry_writes_standardized_jsonl_records(tmp_path):
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260611_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create a review",
        steps=build_default_steps(),
        created_at=now,
        updated_at=now,
    )
    run = create_knowledge_pack_skeleton(run, tmp_path)
    registry = build_default_tool_registry()

    registry.dispatch("research_agent.echo", {"message": "trace me"}, run=run)

    tool_calls_path = Path(run.output_dir) / "assets" / "tool-calls.jsonl"
    payload = json.loads(tool_calls_path.read_text(encoding="utf-8").splitlines()[0])

    for field in (
        "run_id",
        "tool_name",
        "provider",
        "arguments",
        "status",
        "result_summary",
        "error",
        "started_at",
        "completed_at",
        "duration_ms",
        "fallback_used",
    ):
        assert field in payload
    assert payload["run_id"] == "run_20260611_000001"
    assert payload["tool_name"] == "research_agent.echo"
    assert payload["provider"] == "local"
    assert payload["arguments"] == {"message": "trace me"}
    assert payload["status"] == "completed"
    assert payload["error"] is None
    assert payload["fallback_used"] is False
