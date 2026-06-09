import json
from datetime import datetime, timezone

from app.research_workflow.knowledge_pack import (
    create_knowledge_pack_skeleton,
    slugify_run_name,
)
from app.research_workflow.schemas import (
    DEFAULT_RESEARCH_RUN_STEPS,
    ResearchRun,
    ResearchRunArtifact,
    ResearchRunCreateRequest,
    ResearchRunOptions,
    build_default_steps,
)
from app.research_workflow.service import ResearchRunService
from app.research_workflow.service import ResearchRunConflictError
from app.research_workflow.service import ResearchRunNotFoundError
from app.research_workflow.store import FileResearchRunStore


def test_research_run_create_request_defaults():
    req = ResearchRunCreateRequest(
        collection_id="COLL123",
        collection_name="IRSTD",
    )

    assert (
        req.goal
        == "Generate a literature review and experiment plan from this Zotero collection."
    )
    assert req.options.max_papers == 5
    assert req.options.semantic_scholar is False
    assert req.options.arxiv is False
    assert req.options.obsidian_publish is False


def test_build_default_steps_uses_expected_agents():
    steps = build_default_steps()

    assert [step.step_id for step in steps] == [
        item[0] for item in DEFAULT_RESEARCH_RUN_STEPS
    ]
    assert [step.agent for step in steps] == [
        item[1] for item in DEFAULT_RESEARCH_RUN_STEPS
    ]
    assert all(step.status == "queued" for step in steps)


def test_research_run_model_accepts_artifact_paths():
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create a review",
        options=ResearchRunOptions(max_papers=3),
        steps=build_default_steps(),
        artifacts=[
            {
                "label": "Run Summary",
                "path": "ResearchAgent/Runs/demo/00 Run Summary.md",
                "kind": "markdown",
            }
        ],
        output_dir="ResearchAgent/Runs/demo",
        created_at=now,
        updated_at=now,
    )

    assert run.source == "zotero_collection"
    assert run.status == "queued"
    assert run.artifacts[0].label == "Run Summary"


def test_slugify_run_name_keeps_ascii_and_replaces_spaces():
    assert slugify_run_name("IRSTD Literature Review") == "irstd-literature-review"
    assert slugify_run_name("  A/B: RAG + MCP  ") == "a-b-rag-mcp"
    assert slugify_run_name("") == "research-run"
    assert slugify_run_name("  +/:  ") == "research-run"


def test_create_knowledge_pack_skeleton_writes_expected_files(tmp_path):
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create an IRSTD review",
        options=ResearchRunOptions(semantic_scholar=True, arxiv=True, max_papers=3),
        steps=build_default_steps(),
        created_at=now,
        updated_at=now,
    )

    updated = create_knowledge_pack_skeleton(run, tmp_path)

    output_dir = (
        tmp_path / "ResearchAgent" / "Runs" / "run-20260609-000001-irstd"
    )
    assert output_dir.is_dir()
    assert (output_dir / "00 Run Summary.md").is_file()
    assert (output_dir / "papers").is_dir()
    assert (output_dir / "assets" / "trace.json").is_file()
    assert (output_dir / "assets" / "tool-calls.jsonl").is_file()
    assert "Create an IRSTD review" in (
        output_dir / "00 Run Summary.md"
    ).read_text(encoding="utf-8")

    trace = json.loads(
        (output_dir / "assets" / "trace.json").read_text(encoding="utf-8")
    )
    assert trace["run_id"] == "run_20260609_000001"
    assert trace["steps"][0]["agent"] == "CollectionIntakeAgent"
    assert updated.output_dir == str(output_dir)
    assert {artifact.label for artifact in updated.artifacts} == {
        "Knowledge Pack",
        "Run Summary",
        "Trace",
        "Tool Calls",
    }
    assert {artifact.label: artifact.kind for artifact in updated.artifacts} == {
        "Knowledge Pack": "directory",
        "Run Summary": "markdown",
        "Trace": "json",
        "Tool Calls": "jsonl",
    }


def test_create_knowledge_pack_skeleton_preserves_existing_tool_calls(tmp_path):
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create an IRSTD review",
        steps=build_default_steps(),
        created_at=now,
        updated_at=now,
    )
    updated = create_knowledge_pack_skeleton(run, tmp_path)
    tool_calls_path = (
        tmp_path
        / "ResearchAgent"
        / "Runs"
        / "run-20260609-000001-irstd"
        / "assets"
        / "tool-calls.jsonl"
    )
    existing_content = '{"tool": "zotero", "status": "ok"}\n'
    tool_calls_path.write_text(existing_content, encoding="utf-8")

    repeated = create_knowledge_pack_skeleton(updated, tmp_path)

    assert tool_calls_path.read_text(encoding="utf-8") == existing_content
    assert repeated.output_dir == updated.output_dir


def test_create_knowledge_pack_skeleton_preserves_existing_summary_and_trace(tmp_path):
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create an IRSTD review",
        steps=build_default_steps(),
        created_at=now,
        updated_at=now,
    )
    updated = create_knowledge_pack_skeleton(run, tmp_path)
    output_dir = (
        tmp_path
        / "ResearchAgent"
        / "Runs"
        / "run-20260609-000001-irstd"
    )
    summary_path = output_dir / "00 Run Summary.md"
    trace_path = output_dir / "assets" / "trace.json"
    summary_content = "# Curated summary\n\nUser-edited notes.\n"
    trace_content = '{"custom": true}\n'
    summary_path.write_text(summary_content, encoding="utf-8")
    trace_path.write_text(trace_content, encoding="utf-8")

    repeated = create_knowledge_pack_skeleton(updated, tmp_path)

    assert summary_path.read_text(encoding="utf-8") == summary_content
    assert trace_path.read_text(encoding="utf-8") == trace_content
    assert repeated.output_dir == updated.output_dir


def test_create_knowledge_pack_skeleton_preserves_non_skeleton_artifacts(tmp_path):
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create an IRSTD review",
        steps=build_default_steps(),
        artifacts=[
            ResearchRunArtifact(
                label="Generated Literature Matrix",
                path="ResearchAgent/Runs/custom/method-matrix.md",
                kind="markdown",
            )
        ],
        created_at=now,
        updated_at=now,
    )

    updated = create_knowledge_pack_skeleton(run, tmp_path)

    artifacts_by_label = {artifact.label: artifact for artifact in updated.artifacts}
    assert "Generated Literature Matrix" in artifacts_by_label
    assert artifacts_by_label["Generated Literature Matrix"].path == (
        "ResearchAgent/Runs/custom/method-matrix.md"
    )
    assert set(artifacts_by_label) == {
        "Generated Literature Matrix",
        "Knowledge Pack",
        "Run Summary",
        "Trace",
        "Tool Calls",
    }


def test_research_run_service_create_run_initializes_queued_run(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")

    run = service.create_run(
        ResearchRunCreateRequest(
            collection_id="COLL123",
            collection_name="IRSTD",
            goal="Create a review",
            options=ResearchRunOptions(max_papers=2),
        )
    )

    assert run.run_id.startswith("run_")
    assert run.status == "queued"
    assert len(run.steps) == 5
    assert "irstd" in run.output_dir.lower()
    assert store.get(run.run_id).output_dir == run.output_dir


def test_research_run_service_list_runs_includes_created_run(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")

    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    assert [listed.run_id for listed in service.list_runs()] == [run.run_id]


def test_research_run_service_cancel_queued_run_marks_run_cancelled(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    cancelled = service.cancel_run(run.run_id)

    assert cancelled.status == "cancelled"
    assert cancelled.completed_at is not None
    assert store.get(run.run_id).status == "cancelled"


def test_research_run_service_cancel_persists_returned_artifacts(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )
    run = run.model_copy(
        update={
            "output_dir": "",
            "artifacts": [
                ResearchRunArtifact(
                    label="Generated Literature Matrix",
                    path="ResearchAgent/Runs/custom/method-matrix.md",
                    kind="markdown",
                )
            ],
        }
    )
    store.upsert(run)

    cancelled = service.cancel_run(run.run_id)
    persisted = store.get(run.run_id)

    assert persisted.output_dir == cancelled.output_dir
    assert persisted.artifacts == cancelled.artifacts
    assert {artifact.label for artifact in persisted.artifacts} == {
        "Generated Literature Matrix",
        "Knowledge Pack",
        "Run Summary",
        "Trace",
        "Tool Calls",
    }


def test_research_run_service_get_missing_run_raises_not_found(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")

    try:
        service.get_run("missing")
    except ResearchRunNotFoundError as exc:
        assert exc.args == ("missing",)
    else:
        raise AssertionError("Expected ResearchRunNotFoundError")


def test_research_run_service_cancel_missing_run_raises_not_found(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")

    try:
        service.cancel_run("missing")
    except ResearchRunNotFoundError as exc:
        assert exc.args == ("missing",)
    else:
        raise AssertionError("Expected ResearchRunNotFoundError")


def test_research_run_service_cancel_terminal_run_raises_conflict(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )
    store.upsert(run.model_copy(update={"status": "completed"}))

    try:
        service.cancel_run(run.run_id)
    except ResearchRunConflictError as exc:
        assert "cannot be cancelled from status completed" in str(exc)
    else:
        raise AssertionError("Expected ResearchRunConflictError")


def test_research_run_service_repeated_cancel_raises_conflict(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    service.cancel_run(run.run_id)

    try:
        service.cancel_run(run.run_id)
    except ResearchRunConflictError as exc:
        assert "cannot be cancelled from status cancelled" in str(exc)
    else:
        raise AssertionError("Expected ResearchRunConflictError")


def test_research_run_service_cancel_marks_running_steps_cancelled(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )
    steps = run.steps
    steps[0] = steps[0].model_copy(
        update={"status": "completed", "completed_at": datetime.now(timezone.utc)}
    )
    steps[1] = steps[1].model_copy(update={"status": "running"})
    steps[2] = steps[2].model_copy(update={"status": "failed"})
    steps[3] = steps[3].model_copy(update={"status": "cancelled"})
    store.upsert(run.model_copy(update={"status": "running", "steps": steps}))

    cancelled = service.cancel_run(run.run_id)

    assert [step.status for step in cancelled.steps] == [
        "completed",
        "cancelled",
        "failed",
        "cancelled",
        "cancelled",
    ]
    assert cancelled.steps[1].completed_at is not None
    assert cancelled.steps[1].message == "Cancelled before execution"
    assert cancelled.steps[4].completed_at is not None
