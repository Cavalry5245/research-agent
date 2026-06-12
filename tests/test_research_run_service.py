import json
from datetime import datetime, timezone
from pathlib import Path

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
from app.research_workflow.tool_registry import ToolRegistry


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


def test_research_run_model_defaults_to_no_paper_items():
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create a review",
        steps=build_default_steps(),
        created_at=now,
        updated_at=now,
    )

    assert run.paper_items == []


def test_research_run_paper_item_tracks_item_lifecycle():
    from app.research_workflow.schemas import (
        ResearchRunPaperArtifact,
        ResearchRunPaperItem,
    )

    now = datetime.now(timezone.utc)
    item = ResearchRunPaperItem(
        item_id="zotero_ABCD1234",
        title="Grounding DINO for Infrared Small Target Detection",
        zotero_item_id="ABCD1234",
        paper_id="paper_20260609_001",
        pdf_path="app/storage/papers/demo.pdf",
        metadata={"doi": "10.1234/demo", "year": 2025},
        status="completed",
        progress=1.0,
        artifacts=[
            ResearchRunPaperArtifact(
                label="Paper Note",
                path="ResearchAgent/Runs/demo/papers/paper_20260609_001.md",
                kind="markdown",
            )
        ],
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=now,
    )

    assert item.item_id == "zotero_ABCD1234"
    assert item.status == "completed"
    assert item.artifacts[0].kind == "markdown"


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
    assert {artifact["label"] for artifact in trace["artifacts"]} == {
        "Knowledge Pack",
        "Run Summary",
        "Trace",
        "Tool Calls",
    }
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


def test_knowledge_pack_update_rewrites_summary_with_paper_counts(tmp_path):
    from app.research_workflow.knowledge_pack import update_knowledge_pack_run_files
    from app.research_workflow.schemas import ResearchRunPaperItem

    now = datetime.now(timezone.utc)
    steps = build_default_steps()
    steps[0].status = "running"
    steps[0].progress = 0.25
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create an IRSTD review",
        progress=0.5,
        steps=steps,
        paper_items=[
            ResearchRunPaperItem(
                item_id="zotero_A1",
                title="Paper A",
                zotero_item_id="A1",
                paper_id="paper_20260609_001",
                status="completed",
                progress=1.0,
                created_at=now,
                updated_at=now,
            ),
            ResearchRunPaperItem(
                item_id="zotero_B2",
                title="Paper B",
                zotero_item_id="B2",
                status="skipped",
                progress=1.0,
                error="No local PDF attachment found",
                created_at=now,
                updated_at=now,
            ),
        ],
        created_at=now,
        updated_at=now,
    )
    run = create_knowledge_pack_skeleton(run, tmp_path)

    update_knowledge_pack_run_files(run)

    summary = (Path(run.output_dir) / "00 Run Summary.md").read_text(
        encoding="utf-8"
    )
    trace = json.loads(
        (Path(run.output_dir) / "assets" / "trace.json").read_text(
            encoding="utf-8"
        )
    )
    assert "- Completed Papers: 1" in summary
    assert "- Skipped Papers: 1" in summary
    assert "- Progress: 50%" in summary
    assert "- CollectionIntakeAgent: running (25%)" in summary
    assert "Paper A" in summary
    assert "No local PDF attachment found" in summary
    assert trace["paper_items"][0]["paper_id"] == "paper_20260609_001"


def test_append_tool_call_record_writes_jsonl(tmp_path):
    from app.research_workflow.knowledge_pack import append_tool_call_record

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
    run = create_knowledge_pack_skeleton(run, tmp_path)

    append_tool_call_record(
        run,
        {
            "tool_name": "zotero.list_collection_items",
            "provider": "local_http",
            "status": "completed",
            "result_summary": "2 items",
        },
    )

    lines = (
        (Path(run.output_dir) / "assets" / "tool-calls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["run_id"] == "run_20260609_000001"
    assert payload["tool_name"] == "zotero.list_collection_items"


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


def test_research_run_service_execute_local_run_processes_success_and_skip(tmp_path):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path=str(tmp_path / "a.pdf"),
                    created_at=now,
                    updated_at=now,
                ),
                ResearchRunPaperItem(
                    item_id="zotero_B2",
                    title="Paper B",
                    zotero_item_id="B2",
                    status="skipped",
                    progress=1.0,
                    error="No local PDF attachment found",
                    created_at=now,
                    updated_at=now,
                    completed_at=now,
                ),
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            completed = item.model_copy(
                update={
                    "paper_id": "paper_20260609_001",
                    "status": "completed",
                    "progress": 1.0,
                    "updated_at": datetime.now(timezone.utc),
                    "completed_at": datetime.now(timezone.utc),
                }
            )
            return PaperProcessingResult(
                item=completed,
                chunk_count=2,
                note_path="note.md",
                vector_backend="fake",
            )

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(
            collection_id="COLL123",
            collection_name="IRSTD",
            options=ResearchRunOptions(max_papers=2),
        )
    )

    executed = service.execute_local_run(
        run.run_id, intake_service=FakeIntake(), paper_processor=FakeProcessor()
    )

    assert executed.status == "completed"
    assert executed.progress == 1.0
    assert [item.status for item in executed.paper_items] == ["completed", "skipped"]
    assert executed.steps[0].status == "completed"
    assert executed.steps[1].status == "completed"
    assert store.get(run.run_id).paper_items[0].paper_id == "paper_20260609_001"
    summary = (Path(executed.output_dir) / "00 Run Summary.md").read_text(
        encoding="utf-8"
    )
    assert "- Completed Papers: 1" in summary
    assert "- Skipped Papers: 1" in summary


def test_research_run_service_uses_zotero_mcp_when_available(tmp_path, monkeypatch):
    from app.research_workflow.zotero_intake import ZoteroCollectionItem

    class FakeMCPManager:
        def list_servers(self):
            return ["zotero"]

    class FakeMCPAdapter:
        def __init__(self, _proxy):
            pass

        def list_collection_items(self, _collection_id):
            return [
                ZoteroCollectionItem(
                    key="MCP12345",
                    title="MCP Paper",
                    attachments=[],
                )
            ]

    monkeypatch.setattr("app.research_workflow.service.ZoteroMCPAdapter", FakeMCPAdapter)

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
    assert executed.paper_items[0].title == "MCP Paper"
    records = [
        json.loads(line)
        for line in (Path(executed.output_dir) / "assets" / "tool-calls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert records[0]["provider"] == "zotero_mcp"
    assert records[0]["fallback_used"] is False


def test_research_run_service_uses_http_fallback_when_zotero_mcp_unavailable(
    tmp_path,
    monkeypatch,
):
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
    records = [
        json.loads(line)
        for line in (Path(executed.output_dir) / "assets" / "tool-calls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert records[0]["provider"] == "local_http"
    assert records[0]["fallback_used"] is True


def test_research_run_service_can_start_optional_mcp_servers(tmp_path, monkeypatch):
    started = []

    class FakeManager:
        def start_server(self, config):
            started.append((config.name, config.command))

        def list_servers(self):
            return [name for name, _command in started]

        def shutdown_all(self):
            pass

    monkeypatch.setattr("app.research_workflow.service.MCPClientManager", FakeManager)
    monkeypatch.setattr(
        "app.research_workflow.service.ensure_zotero_mcp_installed",
        lambda _command="": (False, "disabled"),
    )
    monkeypatch.setattr("app.research_workflow.service.settings.mcp_enabled", True)
    monkeypatch.setattr("app.research_workflow.service.settings.zotero_mcp_enabled", False)
    monkeypatch.setattr(
        "app.research_workflow.service.settings.semantic_scholar_mcp_enabled",
        True,
    )
    monkeypatch.setattr("app.research_workflow.service.settings.arxiv_mcp_enabled", True)

    ResearchRunService(store=FileResearchRunStore(tmp_path / "runs.json"), vault_root=tmp_path)

    assert (
        "semantic-scholar",
        ["python", "-m", "app.mcp.minimal_semantic_scholar_server"],
    ) in started
    assert ("arxiv", ["python", "-m", "app.mcp.minimal_arxiv_server"]) in started


def test_research_run_service_execute_local_run_marks_intake_exception_failed(
    tmp_path,
):
    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            raise RuntimeError("zotero offline")

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    executed = service.execute_local_run(
        run.run_id,
        intake_service=FakeIntake(),
        paper_processor=object(),
    )

    persisted = store.get(run.run_id)
    assert persisted is not None
    assert executed.status == "failed"
    assert persisted.status == "failed"
    assert persisted.progress == 1.0
    assert persisted.completed_at is not None
    assert "zotero offline" in (persisted.error or "")
    intake_step = persisted.steps[0]
    assert intake_step.step_id == "collection_intake"
    assert intake_step.status == "failed"
    assert intake_step.progress == 1.0
    assert intake_step.completed_at is not None
    assert "zotero offline" in (intake_step.error or "")

    summary = (Path(persisted.output_dir) / "00 Run Summary.md").read_text(
        encoding="utf-8"
    )
    trace = json.loads(
        (Path(persisted.output_dir) / "assets" / "trace.json").read_text(
            encoding="utf-8"
        )
    )
    tool_calls = (
        (Path(persisted.output_dir) / "assets" / "tool-calls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    tool_payload = json.loads(tool_calls[0])
    assert "- Status: failed" in summary
    assert "- CollectionIntakeAgent: failed (100%)" in summary
    assert trace["status"] == "failed"
    assert trace["steps"][0]["status"] == "failed"
    assert "zotero offline" in trace["steps"][0]["error"]
    assert tool_payload["tool_name"] == "zotero.list_collection_items"
    assert tool_payload["status"] == "failed"
    assert "zotero offline" in tool_payload["result_summary"]


def test_research_run_service_execute_local_run_keeps_going_after_item_failure(
    tmp_path,
):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path="a.pdf",
                    created_at=now,
                    updated_at=now,
                ),
                ResearchRunPaperItem(
                    item_id="zotero_B2",
                    title="Paper B",
                    zotero_item_id="B2",
                    pdf_path="b.pdf",
                    created_at=now,
                    updated_at=now,
                ),
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            now = datetime.now(timezone.utc)
            if item.zotero_item_id == "A1":
                raise RuntimeError("parse exploded")
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "paper_20260609_002",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": now,
                        "completed_at": now,
                    }
                ),
                chunk_count=1,
            )

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    executed = service.execute_local_run(
        run.run_id, intake_service=FakeIntake(), paper_processor=FakeProcessor()
    )

    assert executed.status == "completed"
    assert [item.status for item in executed.paper_items] == ["failed", "completed"]
    assert "parse exploded" in (executed.paper_items[0].error or "")
    assert executed.paper_items[1].paper_id == "paper_20260609_002"


def test_research_run_service_execute_local_run_records_registry_tool_fields(
    tmp_path,
):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path="a.pdf",
                    created_at=now,
                    updated_at=now,
                )
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            now = datetime.now(timezone.utc)
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "paper_20260611_001",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": now,
                        "completed_at": now,
                    }
                ),
                chunk_count=1,
            )

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    executed = service.execute_local_run(
        run.run_id,
        intake_service=FakeIntake(),
        paper_processor=FakeProcessor(),
    )

    records = [
        json.loads(line)
        for line in (
            Path(executed.output_dir) / "assets" / "tool-calls.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert records
    for record in records:
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
            assert field in record
    assert records[0]["tool_name"] == "zotero.list_collection_items"
    assert records[0]["arguments"] == {"collection_id": "COLL123", "max_papers": 5}
    assert records[1]["tool_name"] == "research_agent.process_paper"
    assert records[1]["result_summary"] == "paper_20260611_001"


def test_research_run_service_execute_local_run_dispatches_registry_tools(
    tmp_path,
):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path="a.pdf",
                    created_at=now,
                    updated_at=now,
                )
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            now = datetime.now(timezone.utc)
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "paper_20260611_001",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": now,
                        "completed_at": now,
                    }
                ),
                chunk_count=1,
            )

    registry = ToolRegistry()
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(
        store=store,
        vault_root=tmp_path / "vault",
        tool_registry_factory=lambda: registry,
    )
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    service.execute_local_run(
        run.run_id,
        intake_service=FakeIntake(),
        paper_processor=FakeProcessor(),
    )

    assert [record["tool_name"] for record in registry.call_records()] == [
        "zotero.list_collection_items",
        "research_agent.process_paper",
        "research_agent.generate_knowledge_pack",
        "obsidian.publish_knowledge_pack",
    ]


def test_research_run_service_execute_local_run_generates_knowledge_pack_outputs(
    tmp_path,
):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path="a.pdf",
                    metadata={"year": 2025, "doi": "10.1234/a"},
                    created_at=now,
                    updated_at=now,
                )
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            now = datetime.now(timezone.utc)
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "paper_20260611_001",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": now,
                        "completed_at": now,
                    }
                ),
                chunk_count=1,
            )

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    executed = service.execute_local_run(
        run.run_id,
        intake_service=FakeIntake(),
        paper_processor=FakeProcessor(),
    )

    output_dir = Path(executed.output_dir)
    expected_files = [
        "01 Literature Review.md",
        "02 Method Matrix.md",
        "03 Research Gaps.md",
        "04 Experiment Plan.md",
        "05 Reading Roadmap.md",
    ]
    for filename in expected_files:
        assert (output_dir / filename).is_file()
    steps_by_id = {step.step_id: step for step in executed.steps}
    assert steps_by_id["literature_synthesis"].status == "completed"
    assert steps_by_id["experiment_planning"].status == "completed"
    assert steps_by_id["obsidian_publishing"].status == "completed"
    artifact_labels = {artifact.label for artifact in executed.artifacts}
    assert {
        "Literature Review",
        "Method Matrix",
        "Research Gaps",
        "Experiment Plan",
        "Reading Roadmap",
    }.issubset(artifact_labels)
    summary = (output_dir / "00 Run Summary.md").read_text(encoding="utf-8")
    trace = json.loads((output_dir / "assets" / "trace.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (output_dir / "assets" / "tool-calls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert "Literature Review" in summary
    assert any(artifact["label"] == "Experiment Plan" for artifact in trace["artifacts"])
    assert any(
        record["tool_name"] == "research_agent.generate_knowledge_pack"
        for record in records
    )
    assert any(record["tool_name"] == "obsidian.publish_knowledge_pack" for record in records)


def test_research_run_service_execute_local_run_persists_synthesis_failure(
    tmp_path,
    monkeypatch,
):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem
    from app.research_workflow import service as service_module

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path="a.pdf",
                    created_at=now,
                    updated_at=now,
                )
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            now = datetime.now(timezone.utc)
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "paper_20260611_001",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": now,
                        "completed_at": now,
                    }
                ),
                chunk_count=1,
            )

    class ExplodingSynthesisService:
        def generate(self, run):
            raise RuntimeError("synthesis exploded")

    monkeypatch.setattr(
        service_module,
        "KnowledgePackSynthesisService",
        lambda: ExplodingSynthesisService(),
    )

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    executed = service.execute_local_run(
        run.run_id,
        intake_service=FakeIntake(),
        paper_processor=FakeProcessor(),
    )

    persisted = store.get(run.run_id)
    steps_by_id = {step.step_id: step for step in persisted.steps}
    records = [
        json.loads(line)
        for line in (Path(persisted.output_dir) / "assets" / "tool-calls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert executed.status == "failed"
    assert persisted.status == "failed"
    assert "synthesis exploded" in (persisted.error or "")
    assert steps_by_id["literature_synthesis"].status == "failed"
    assert "synthesis exploded" in (steps_by_id["literature_synthesis"].error or "")
    assert any(
        record["tool_name"] == "research_agent.generate_knowledge_pack"
        and record["status"] == "failed"
        and "synthesis exploded" in (record["error"] or "")
        for record in records
    )


def test_research_run_service_execute_local_run_persists_obsidian_publish_failure(
    tmp_path,
    monkeypatch,
):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem
    from app.research_workflow import service as service_module

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path="a.pdf",
                    created_at=now,
                    updated_at=now,
                )
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            now = datetime.now(timezone.utc)
            return PaperProcessingResult(
                item=item.model_copy(
                    update={
                        "paper_id": "paper_20260611_001",
                        "status": "completed",
                        "progress": 1.0,
                        "updated_at": now,
                        "completed_at": now,
                    }
                ),
                chunk_count=1,
            )

    class ExplodingObsidianAdapter:
        def __init__(self, vault_root):
            self.vault_root = vault_root

        def publish_markdown(self, note_name, content):
            raise RuntimeError("obsidian unavailable")

    monkeypatch.setattr(service_module, "ObsidianAdapter", ExplodingObsidianAdapter)

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(
            collection_id="COLL123",
            collection_name="IRSTD",
            options=ResearchRunOptions(
                obsidian_publish=True,
                obsidian_vault_path=str(tmp_path / "obsidian"),
            ),
        )
    )

    executed = service.execute_local_run(
        run.run_id,
        intake_service=FakeIntake(),
        paper_processor=FakeProcessor(),
    )

    persisted = store.get(run.run_id)
    steps_by_id = {step.step_id: step for step in persisted.steps}
    records = [
        json.loads(line)
        for line in (Path(persisted.output_dir) / "assets" / "tool-calls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert executed.status == "failed"
    assert persisted.status == "failed"
    assert "obsidian unavailable" in (persisted.error or "")
    assert steps_by_id["literature_synthesis"].status == "completed"
    assert steps_by_id["obsidian_publishing"].status == "failed"
    assert "obsidian unavailable" in (steps_by_id["obsidian_publishing"].error or "")
    assert any(
        record["tool_name"] == "obsidian.publish_knowledge_pack"
        and record["status"] == "failed"
        and "obsidian unavailable" in (record["error"] or "")
        for record in records
    )
