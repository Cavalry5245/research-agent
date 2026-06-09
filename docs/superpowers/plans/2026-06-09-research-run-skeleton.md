# Research Run Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Milestone 1 from the approved design: a visible Research Run workflow spine that can create, persist, monitor, and render a skeleton Zotero-to-Obsidian research run without invoking LLMs or external MCP servers.

**Architecture:** Add a focused workflow package under `app/research_workflow/` for run models, persistence, and knowledge-pack skeleton generation. Expose the workflow through a new FastAPI router under `/research-runs`, then add a Streamlit launcher/monitor page that calls the same services directly for the local UI. Keep existing upload, QA, comparison, Zotero, and Agent pages intact.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Streamlit, JSON file persistence, pytest, FastAPI TestClient.

---

## Scope

This plan implements only the first milestone from `docs/superpowers/specs/2026-06-09-research-agent-mcp-workflow-design.md`.

Included:

- `ResearchRun` schemas and status model.
- File-backed run store.
- Knowledge Pack directory skeleton.
- Run service that creates a run and writes `00 Run Summary.md`, `assets/trace.json`, and `assets/tool-calls.jsonl`.
- FastAPI routes for create/list/get/cancel.
- Streamlit workflow launcher and monitor.

Excluded until later plans:

- Zotero collection item processing.
- PDF parsing inside a research run.
- LLM-generated literature review.
- ResearchAgent MCP Server.
- Obsidian MCP publishing.
- Semantic Scholar and arXiv integrations.

## File Structure

- Create: `app/research_workflow/__init__.py`
  - Package marker and public import surface.
- Create: `app/research_workflow/schemas.py`
  - Pydantic request/response/domain models for research runs.
- Create: `app/research_workflow/store.py`
  - `FileResearchRunStore` with JSON persistence and deterministic sorting.
- Create: `app/research_workflow/knowledge_pack.py`
  - Slug generation, folder creation, and skeleton Markdown/trace assets.
- Create: `app/research_workflow/service.py`
  - Orchestrates run creation, listing, lookup, cancellation, and artifact initialization.
- Create: `app/routers/research_runs.py`
  - FastAPI endpoints under `/research-runs`.
- Modify: `app/main.py`
  - Include the new router.
- Modify: `ui/streamlit_app.py`
  - Add a new first sidebar page: `Research Workflow`.
  - Render a launcher and run monitor using the service.
- Test: `tests/test_research_run_store.py`
  - Store persistence and sorting.
- Test: `tests/test_research_run_service.py`
  - Run creation, skeleton artifact generation, cancellation.
- Test: `tests/test_research_run_router.py`
  - API create/list/get/cancel behavior.

## Data Model

Use these exact model names and field names.

```python
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ResearchRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class ResearchRunOptions(BaseModel):
    semantic_scholar: bool = False
    arxiv: bool = False
    obsidian_publish: bool = False
    max_papers: int = Field(default=5, ge=1, le=50)
    obsidian_vault_path: str | None = None


class ResearchRunStep(BaseModel):
    step_id: str
    agent: str
    status: ResearchRunStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ResearchRunArtifact(BaseModel):
    label: str
    path: str
    kind: Literal["markdown", "json", "jsonl", "directory"]


class ResearchRun(BaseModel):
    run_id: str
    goal: str
    source: Literal["zotero_collection"] = "zotero_collection"
    collection_id: str
    collection_name: str
    status: ResearchRunStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    options: ResearchRunOptions = Field(default_factory=ResearchRunOptions)
    steps: list[ResearchRunStep] = Field(default_factory=list)
    artifacts: list[ResearchRunArtifact] = Field(default_factory=list)
    output_dir: str = ""
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ResearchRunCreateRequest(BaseModel):
    collection_id: str
    collection_name: str
    goal: str = "Generate a literature review and experiment plan from this Zotero collection."
    options: ResearchRunOptions = Field(default_factory=ResearchRunOptions)


class ResearchRunListResponse(BaseModel):
    count: int
    runs: list[ResearchRun]
```

Default steps:

```python
DEFAULT_RESEARCH_RUN_STEPS = [
    ("collection_intake", "CollectionIntakeAgent"),
    ("paper_understanding", "PaperUnderstandingAgent"),
    ("literature_synthesis", "LiteratureSynthesisAgent"),
    ("experiment_planning", "ExperimentPlanningAgent"),
    ("obsidian_publishing", "ObsidianPublishingAgent"),
]
```

## Task 1: Add Research Run Schemas

**Files:**

- Create: `app/research_workflow/__init__.py`
- Create: `app/research_workflow/schemas.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Write schema tests**

Add this test file content if the file does not exist yet:

```python
from datetime import datetime, timezone

from app.research_workflow.schemas import (
    DEFAULT_RESEARCH_RUN_STEPS,
    ResearchRun,
    ResearchRunCreateRequest,
    ResearchRunOptions,
    build_default_steps,
)


def test_research_run_create_request_defaults():
    req = ResearchRunCreateRequest(
        collection_id="COLL123",
        collection_name="IRSTD",
    )

    assert req.goal == "Generate a literature review and experiment plan from this Zotero collection."
    assert req.options.max_papers == 5
    assert req.options.semantic_scholar is False
    assert req.options.arxiv is False
    assert req.options.obsidian_publish is False


def test_build_default_steps_uses_expected_agents():
    steps = build_default_steps()

    assert [step.step_id for step in steps] == [item[0] for item in DEFAULT_RESEARCH_RUN_STEPS]
    assert [step.agent for step in steps] == [item[1] for item in DEFAULT_RESEARCH_RUN_STEPS]
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
            {"label": "Run Summary", "path": "ResearchAgent/Runs/demo/00 Run Summary.md", "kind": "markdown"}
        ],
        output_dir="ResearchAgent/Runs/demo",
        created_at=now,
        updated_at=now,
    )

    assert run.source == "zotero_collection"
    assert run.status == "queued"
    assert run.artifacts[0].label == "Run Summary"
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.research_workflow'`.

- [ ] **Step 3: Create the package marker**

Create `app/research_workflow/__init__.py`:

```python
"""Research workflow orchestration package."""
```

- [ ] **Step 4: Create schemas**

Create `app/research_workflow/schemas.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ResearchRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

DEFAULT_RESEARCH_RUN_STEPS = [
    ("collection_intake", "CollectionIntakeAgent"),
    ("paper_understanding", "PaperUnderstandingAgent"),
    ("literature_synthesis", "LiteratureSynthesisAgent"),
    ("experiment_planning", "ExperimentPlanningAgent"),
    ("obsidian_publishing", "ObsidianPublishingAgent"),
]


class ResearchRunOptions(BaseModel):
    semantic_scholar: bool = False
    arxiv: bool = False
    obsidian_publish: bool = False
    max_papers: int = Field(default=5, ge=1, le=50)
    obsidian_vault_path: str | None = None


class ResearchRunStep(BaseModel):
    step_id: str
    agent: str
    status: ResearchRunStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ResearchRunArtifact(BaseModel):
    label: str
    path: str
    kind: Literal["markdown", "json", "jsonl", "directory"]


class ResearchRun(BaseModel):
    run_id: str
    goal: str
    source: Literal["zotero_collection"] = "zotero_collection"
    collection_id: str
    collection_name: str
    status: ResearchRunStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    options: ResearchRunOptions = Field(default_factory=ResearchRunOptions)
    steps: list[ResearchRunStep] = Field(default_factory=list)
    artifacts: list[ResearchRunArtifact] = Field(default_factory=list)
    output_dir: str = ""
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ResearchRunCreateRequest(BaseModel):
    collection_id: str
    collection_name: str
    goal: str = "Generate a literature review and experiment plan from this Zotero collection."
    options: ResearchRunOptions = Field(default_factory=ResearchRunOptions)


class ResearchRunListResponse(BaseModel):
    count: int
    runs: list[ResearchRun]


def build_default_steps() -> list[ResearchRunStep]:
    return [
        ResearchRunStep(step_id=step_id, agent=agent)
        for step_id, agent in DEFAULT_RESEARCH_RUN_STEPS
    ]
```

- [ ] **Step 5: Run schema tests and verify they pass**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py -q
```

Expected: PASS for the three schema tests.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add app/research_workflow/__init__.py app/research_workflow/schemas.py tests/test_research_run_service.py
git commit -m "feat: add research run schemas"
```

## Task 2: Add FileResearchRunStore

**Files:**

- Create: `app/research_workflow/store.py`
- Test: `tests/test_research_run_store.py`

- [ ] **Step 1: Write store tests**

Create `tests/test_research_run_store.py`:

```python
from datetime import datetime, timezone

from app.research_workflow.schemas import ResearchRun, build_default_steps
from app.research_workflow.store import FileResearchRunStore


def _run(run_id: str, collection_name: str, created_at: datetime) -> ResearchRun:
    return ResearchRun(
        run_id=run_id,
        collection_id=f"{run_id}_collection",
        collection_name=collection_name,
        goal="Create a review",
        steps=build_default_steps(),
        output_dir=f"ResearchAgent/Runs/{run_id}",
        created_at=created_at,
        updated_at=created_at,
    )


def test_file_research_run_store_persists_runs(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)
    now = datetime.now(timezone.utc)

    saved = store.upsert(_run("run_a", "IRSTD", now))
    reloaded = FileResearchRunStore(path)

    assert saved.run_id == "run_a"
    assert reloaded.get("run_a").collection_name == "IRSTD"


def test_file_research_run_store_lists_newest_first(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)
    older = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 6, 9, 2, 0, tzinfo=timezone.utc)

    store.upsert(_run("run_old", "Old", older))
    store.upsert(_run("run_new", "New", newer))

    assert [run.run_id for run in store.list()] == ["run_new", "run_old"]


def test_file_research_run_store_clear(tmp_path):
    path = tmp_path / "research_runs.json"
    store = FileResearchRunStore(path)
    now = datetime.now(timezone.utc)
    store.upsert(_run("run_a", "IRSTD", now))

    store.clear()

    assert store.list() == []
    assert store.get("run_a") is None
```

- [ ] **Step 2: Run store tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_store.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.research_workflow.store'`.

- [ ] **Step 3: Implement FileResearchRunStore**

Create `app/research_workflow/store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.research_workflow.schemas import ResearchRun


class FileResearchRunStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, run: ResearchRun) -> ResearchRun:
        with self._lock:
            runs = self._load_unlocked()
            runs[run.run_id] = run
            self._save_unlocked(runs)
        return run

    def get(self, run_id: str) -> ResearchRun | None:
        with self._lock:
            return self._load_unlocked().get(run_id)

    def list(self) -> list[ResearchRun]:
        with self._lock:
            runs = self._load_unlocked()
            return sorted(runs.values(), key=lambda run: run.created_at, reverse=True)

    def clear(self) -> None:
        with self._lock:
            self._save_unlocked({})

    def _load_unlocked(self) -> dict[str, ResearchRun]:
        if not self._path.exists():
            return {}
        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        payload = json.loads(raw)
        runs: dict[str, ResearchRun] = {}
        for item in payload.get("runs", []):
            run = ResearchRun.model_validate(item)
            runs[run.run_id] = run
        return runs

    def _save_unlocked(self, runs: dict[str, ResearchRun]) -> None:
        payload = {
            "runs": [run.model_dump(mode="json") for run in runs.values()],
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run store tests and verify they pass**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add app/research_workflow/store.py tests/test_research_run_store.py
git commit -m "feat: persist research runs"
```

## Task 3: Add Knowledge Pack Skeleton Writer

**Files:**

- Create: `app/research_workflow/knowledge_pack.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Add knowledge pack tests**

Append these tests to `tests/test_research_run_service.py`:

```python
import json

from app.research_workflow.knowledge_pack import (
    create_knowledge_pack_skeleton,
    slugify_run_name,
)
from app.research_workflow.schemas import ResearchRun, ResearchRunOptions, build_default_steps


def test_slugify_run_name_keeps_ascii_and_replaces_spaces():
    assert slugify_run_name("IRSTD Literature Review") == "irstd-literature-review"
    assert slugify_run_name("  A/B: RAG + MCP  ") == "a-b-rag-mcp"


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

    output_dir = tmp_path / "ResearchAgent" / "Runs" / "run-20260609-000001-irstd"
    assert output_dir.is_dir()
    assert (output_dir / "00 Run Summary.md").is_file()
    assert (output_dir / "papers").is_dir()
    assert (output_dir / "assets" / "trace.json").is_file()
    assert (output_dir / "assets" / "tool-calls.jsonl").is_file()
    assert "Create an IRSTD review" in (output_dir / "00 Run Summary.md").read_text(encoding="utf-8")

    trace = json.loads((output_dir / "assets" / "trace.json").read_text(encoding="utf-8"))
    assert trace["run_id"] == "run_20260609_000001"
    assert trace["steps"][0]["agent"] == "CollectionIntakeAgent"
    assert updated.output_dir == str(output_dir)
    assert {artifact.label for artifact in updated.artifacts} == {
        "Knowledge Pack",
        "Run Summary",
        "Trace",
        "Tool Calls",
    }
```

- [ ] **Step 2: Run knowledge pack tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.research_workflow.knowledge_pack'`.

- [ ] **Step 3: Implement knowledge pack skeleton writer**

Create `app/research_workflow/knowledge_pack.py`:

```python
from __future__ import annotations

import json
import re
from pathlib import Path

from app.research_workflow.schemas import ResearchRun, ResearchRunArtifact


def slugify_run_name(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "research-run"


def _run_folder_name(run: ResearchRun) -> str:
    run_part = slugify_run_name(run.run_id.replace("_", "-"))
    collection_part = slugify_run_name(run.collection_name)
    return f"{run_part}-{collection_part}"


def create_knowledge_pack_skeleton(run: ResearchRun, vault_root: str | Path) -> ResearchRun:
    root = Path(vault_root)
    output_dir = root / "ResearchAgent" / "Runs" / _run_folder_name(run)
    papers_dir = output_dir / "papers"
    assets_dir = output_dir / "assets"
    papers_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "00 Run Summary.md"
    trace_path = assets_dir / "trace.json"
    tool_calls_path = assets_dir / "tool-calls.jsonl"

    summary_path.write_text(_render_run_summary(run), encoding="utf-8")
    trace_path.write_text(
        json.dumps(_trace_payload(run), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not tool_calls_path.exists():
        tool_calls_path.write_text("", encoding="utf-8")

    updated = run.model_copy(
        update={
            "output_dir": str(output_dir),
            "artifacts": [
                ResearchRunArtifact(label="Knowledge Pack", path=str(output_dir), kind="directory"),
                ResearchRunArtifact(label="Run Summary", path=str(summary_path), kind="markdown"),
                ResearchRunArtifact(label="Trace", path=str(trace_path), kind="json"),
                ResearchRunArtifact(label="Tool Calls", path=str(tool_calls_path), kind="jsonl"),
            ],
        }
    )
    return updated


def _render_run_summary(run: ResearchRun) -> str:
    step_lines = "\n".join(
        f"- [{step.status}] {step.agent}: {step.message or 'waiting'}"
        for step in run.steps
    )
    return f"""# {run.collection_name} Research Run

## Goal
{run.goal}

## Input
- Source: Zotero collection
- Collection ID: `{run.collection_id}`
- Collection name: `{run.collection_name}`
- Max papers: {run.options.max_papers}

## Tool Options
- Semantic Scholar enrichment: {run.options.semantic_scholar}
- arXiv fallback: {run.options.arxiv}
- Obsidian publishing: {run.options.obsidian_publish}

## Status
- Run ID: `{run.run_id}`
- Status: {run.status}
- Progress: {run.progress:.0%}

## Steps
{step_lines}

## Outputs
This skeleton run has initialized the Knowledge Pack folder. Later milestones will add paper notes, literature review, method matrix, research gaps, experiment plan, and reading roadmap.
"""


def _trace_payload(run: ResearchRun) -> dict:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "goal": run.goal,
        "collection": {
            "id": run.collection_id,
            "name": run.collection_name,
        },
        "steps": [step.model_dump(mode="json") for step in run.steps],
        "artifacts": [artifact.model_dump(mode="json") for artifact in run.artifacts],
    }
```

- [ ] **Step 4: Run knowledge pack tests and verify they pass**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add app/research_workflow/knowledge_pack.py tests/test_research_run_service.py
git commit -m "feat: initialize research knowledge packs"
```

## Task 4: Add ResearchRunService

**Files:**

- Create: `app/research_workflow/service.py`
- Modify: `tests/test_research_run_service.py`

- [ ] **Step 1: Add service tests**

Append these tests to `tests/test_research_run_service.py`:

```python
from app.research_workflow.schemas import ResearchRunCreateRequest, ResearchRunOptions
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore


def test_research_run_service_create_run_initializes_store_and_pack(tmp_path):
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
    assert "IRSTD" in run.output_dir
    assert store.get(run.run_id).output_dir == run.output_dir


def test_research_run_service_list_runs(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")

    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    assert service.list_runs()[0].run_id == run.run_id


def test_research_run_service_cancel_queued_run(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    cancelled = service.cancel_run(run.run_id)

    assert cancelled.status == "cancelled"
    assert cancelled.completed_at is not None
    assert store.get(run.run_id).status == "cancelled"
```

- [ ] **Step 2: Run service tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.research_workflow.service'`.

- [ ] **Step 3: Implement ResearchRunService**

Create `app/research_workflow/service.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.research_workflow.knowledge_pack import create_knowledge_pack_skeleton
from app.research_workflow.schemas import (
    ResearchRun,
    ResearchRunCreateRequest,
    build_default_steps,
)
from app.research_workflow.store import FileResearchRunStore


class ResearchRunNotFoundError(KeyError):
    pass


class ResearchRunConflictError(RuntimeError):
    pass


class ResearchRunService:
    def __init__(self, store: FileResearchRunStore, vault_root: str | Path) -> None:
        self._store = store
        self._vault_root = Path(vault_root)

    def create_run(self, request: ResearchRunCreateRequest) -> ResearchRun:
        now = datetime.now(timezone.utc)
        run = ResearchRun(
            run_id=self._new_run_id(now),
            collection_id=request.collection_id,
            collection_name=request.collection_name,
            goal=request.goal,
            options=request.options,
            steps=build_default_steps(),
            created_at=now,
            updated_at=now,
        )
        run = create_knowledge_pack_skeleton(run, self._vault_root)
        return self._store.upsert(run)

    def list_runs(self) -> list[ResearchRun]:
        return self._store.list()

    def get_run(self, run_id: str) -> ResearchRun:
        run = self._store.get(run_id)
        if run is None:
            raise ResearchRunNotFoundError(run_id)
        return run

    def cancel_run(self, run_id: str) -> ResearchRun:
        run = self.get_run(run_id)
        if run.status in {"completed", "failed", "cancelled"}:
            raise ResearchRunConflictError(f"Research run {run_id} cannot be cancelled from status {run.status}")
        now = datetime.now(timezone.utc)
        updated_steps = [
            step.model_copy(
                update={
                    "status": "cancelled",
                    "completed_at": now,
                    "message": step.message or "Cancelled before execution",
                }
            )
            if step.status == "queued"
            else step
            for step in run.steps
        ]
        updated = run.model_copy(
            update={
                "status": "cancelled",
                "progress": 0.0,
                "steps": updated_steps,
                "completed_at": now,
                "updated_at": now,
                "error": "Research run cancelled",
            }
        )
        updated = create_knowledge_pack_skeleton(updated, self._vault_root)
        return self._store.upsert(updated)

    def _new_run_id(self, now: datetime) -> str:
        return f"run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
```

- [ ] **Step 4: Run service tests and verify they pass**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add app/research_workflow/service.py tests/test_research_run_service.py
git commit -m "feat: create research run service"
```

## Task 5: Add FastAPI Research Run Routes

**Files:**

- Create: `app/routers/research_runs.py`
- Modify: `app/main.py`
- Test: `tests/test_research_run_router.py`

- [ ] **Step 1: Write router tests**

Create `tests/test_research_run_router.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore


def test_research_run_routes_create_list_get_and_cancel(tmp_path, monkeypatch):
    from app.routers import research_runs as router

    service = ResearchRunService(
        store=FileResearchRunStore(tmp_path / "runs.json"),
        vault_root=tmp_path / "vault",
    )
    monkeypatch.setattr(router, "_service_instance", service)
    client = TestClient(app)

    create_response = client.post(
        "/research-runs",
        json={
            "collection_id": "COLL123",
            "collection_name": "IRSTD",
            "goal": "Create an IRSTD review",
            "options": {"max_papers": 3, "semantic_scholar": True},
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["collection_id"] == "COLL123"
    assert created["steps"][0]["agent"] == "CollectionIntakeAgent"

    list_response = client.get("/research-runs")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    detail_response = client.get(f"/research-runs/{created['run_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["run_id"] == created["run_id"]

    cancel_response = client.delete(f"/research-runs/{created['run_id']}")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_research_run_detail_missing_returns_404(tmp_path, monkeypatch):
    from app.routers import research_runs as router

    service = ResearchRunService(
        store=FileResearchRunStore(tmp_path / "runs.json"),
        vault_root=tmp_path / "vault",
    )
    monkeypatch.setattr(router, "_service_instance", service)
    client = TestClient(app)

    response = client.get("/research-runs/missing")

    assert response.status_code == 404
```

- [ ] **Step 2: Run router tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py -q
```

Expected: FAIL with `ImportError` for `app.routers.research_runs` or HTTP 404 for `/research-runs`.

- [ ] **Step 3: Implement router**

Create `app/routers/research_runs.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.research_workflow.schemas import (
    ResearchRun,
    ResearchRunCreateRequest,
    ResearchRunListResponse,
)
from app.research_workflow.service import (
    ResearchRunConflictError,
    ResearchRunNotFoundError,
    ResearchRunService,
)
from app.research_workflow.store import FileResearchRunStore

router = APIRouter(prefix="/research-runs", tags=["research-runs"])

_service_instance: ResearchRunService | None = None


def get_research_run_service() -> ResearchRunService:
    global _service_instance
    if _service_instance is None:
        storage_root = Path(settings.metadata_dir).parent
        store = FileResearchRunStore(storage_root / "research_runs.json")
        vault_root = storage_root / "knowledge_packs"
        _service_instance = ResearchRunService(store=store, vault_root=vault_root)
    return _service_instance


@router.post("", response_model=ResearchRun, status_code=status.HTTP_201_CREATED)
def create_research_run(request: ResearchRunCreateRequest):
    return get_research_run_service().create_run(request)


@router.get("", response_model=ResearchRunListResponse)
def list_research_runs():
    runs = get_research_run_service().list_runs()
    return ResearchRunListResponse(count=len(runs), runs=runs)


@router.get("/{run_id}", response_model=ResearchRun)
def get_research_run(run_id: str):
    try:
        return get_research_run_service().get_run(run_id)
    except ResearchRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Research run {run_id} not found") from exc


@router.delete("/{run_id}", response_model=ResearchRun)
def cancel_research_run(run_id: str):
    try:
        return get_research_run_service().cancel_run(run_id)
    except ResearchRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Research run {run_id} not found") from exc
    except ResearchRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

- [ ] **Step 4: Include router in FastAPI app**

Modify `app/main.py` near the existing router includes:

```python
from app.routers.research_runs import router as research_runs_router

app.include_router(research_runs_router)
```

Place it after the Zotero router include so all routers are grouped together.

- [ ] **Step 5: Run router tests and verify they pass**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py -q
```

Expected: PASS.

- [ ] **Step 6: Run OpenAPI smoke test**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_openapi_schema.py tests/test_health_endpoint.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add app/routers/research_runs.py app/main.py tests/test_research_run_router.py
git commit -m "feat: expose research run routes"
```

## Task 6: Add Streamlit Workflow Launcher and Monitor

**Files:**

- Modify: `ui/streamlit_app.py`
- Test: `tests/test_streamlit_upload_flow.py` or new `tests/test_research_workflow_ui_import.py`

- [ ] **Step 1: Write a UI import smoke test**

Create `tests/test_research_workflow_ui_import.py`:

```python
from app.research_workflow.schemas import ResearchRunCreateRequest


def test_research_workflow_request_can_be_built_for_ui():
    req = ResearchRunCreateRequest(
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create a review",
        options={"max_papers": 3, "semantic_scholar": True, "arxiv": False},
    )

    assert req.collection_id == "COLL123"
    assert req.options.max_papers == 3
```

This test is intentionally light because importing Streamlit executes UI code. The functional UI behavior will be verified manually after the app starts.

- [ ] **Step 2: Run UI smoke test**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_workflow_ui_import.py -q
```

Expected: PASS.

- [ ] **Step 3: Add service imports to Streamlit**

Modify `ui/streamlit_app.py` imports:

```python
from pathlib import Path

from app.research_workflow.schemas import ResearchRunCreateRequest, ResearchRunOptions
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore
```

If `Path` is already imported later, keep only one import at the top.

- [ ] **Step 4: Add cached research run service**

Add below the existing cached resources:

```python
@st.cache_resource
def get_research_run_service():
    storage_root = Path(settings.metadata_dir).parent
    return ResearchRunService(
        store=FileResearchRunStore(storage_root / "research_runs.json"),
        vault_root=storage_root / "knowledge_packs",
    )
```

- [ ] **Step 5: Add first sidebar navigation item**

Modify the `st.radio` navigation list so the first item is:

```python
"Research Workflow",
```

Keep all existing items after it.

- [ ] **Step 6: Add Research Workflow page block before the upload page**

Insert this block before the current first page condition:

```python
if tab == "Research Workflow":
    st.header("Research Workflow")
    st.caption("Start from a Zotero collection and initialize a ResearchAgent knowledge pack.")

    service = get_research_run_service()

    with st.form("research_run_form"):
        collection_id = st.text_input("Zotero Collection ID", placeholder="COLL123")
        collection_name = st.text_input("Collection Name", placeholder="IRSTD")
        goal = st.text_area(
            "Goal",
            value="Generate a literature review and experiment plan from this Zotero collection.",
            height=100,
        )
        max_papers = st.number_input("Max papers", min_value=1, max_value=50, value=5)
        semantic_scholar = st.checkbox("Enable Semantic Scholar enrichment", value=False)
        arxiv = st.checkbox("Enable arXiv fallback", value=False)
        obsidian_publish = st.checkbox("Publish to Obsidian", value=False)
        submitted = st.form_submit_button("Initialize Research Run")

    if submitted:
        if not collection_id.strip() or not collection_name.strip():
            st.error("Collection ID and Collection Name are required.")
        else:
            run = service.create_run(
                ResearchRunCreateRequest(
                    collection_id=collection_id.strip(),
                    collection_name=collection_name.strip(),
                    goal=goal.strip(),
                    options=ResearchRunOptions(
                        max_papers=int(max_papers),
                        semantic_scholar=semantic_scholar,
                        arxiv=arxiv,
                        obsidian_publish=obsidian_publish,
                    ),
                )
            )
            st.session_state["selected_research_run_id"] = run.run_id
            st.success(f"Research run initialized: {run.run_id}")

    runs = service.list_runs()
    st.subheader("Recent Runs")
    if not runs:
        st.info("No research runs yet.")
    else:
        selected_run_id = st.selectbox(
            "Select run",
            [run.run_id for run in runs],
            index=0,
            key="research_run_selector",
        )
        run = service.get_run(selected_run_id)
        st.metric("Status", run.status)
        st.progress(run.progress)
        st.write(f"Collection: {run.collection_name}")
        st.write(f"Output: {run.output_dir}")

        st.subheader("Steps")
        for step in run.steps:
            st.write(f"{step.agent}: {step.status} ({step.progress:.0%})")

        st.subheader("Artifacts")
        for artifact in run.artifacts:
            st.write(f"{artifact.label}: {artifact.path}")
```

Change the old first page condition from:

```python
if tab == "馃摛 璁烘枃涓婁紶":
```

to:

```python
elif tab == "馃摛 璁烘枃涓婁紶":
```

Use the exact existing garbled string from the file for the upload tab; do not retype unrelated labels.

- [ ] **Step 7: Run focused non-UI tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_workflow_ui_import.py tests/test_research_run_service.py tests/test_research_run_store.py -q
```

Expected: PASS.

- [ ] **Step 8: Manually verify Streamlit starts**

Run if Streamlit is not already running:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m streamlit run ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

Expected:

- The app starts without import errors.
- Sidebar includes `Research Workflow`.
- Creating a run with dummy collection values shows a new run and artifact paths.

- [ ] **Step 9: Commit Task 6**

Run:

```powershell
git add ui/streamlit_app.py tests/test_research_workflow_ui_import.py
git commit -m "feat: add research workflow launcher"
```

## Task 7: Milestone 1 Verification

**Files:**

- Modify only if a previous task exposed a bug.

- [ ] **Step 1: Run all Research Run tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py tests/test_research_run_store.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py -q
```

Expected: PASS.

- [ ] **Step 2: Run related API and routing tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_health_endpoint.py tests/test_openapi_schema.py tests/test_zotero_router.py tests/test_task_routes.py -q
```

Expected: PASS.

- [ ] **Step 3: Inspect git diff**

Run:

```powershell
git diff --stat
```

Expected:

- Only planned files from this implementation are changed, plus any pre-existing unrelated dirty files remain unstaged.
- No `.env` changes.
- No deletions.

- [ ] **Step 4: Update task tracking**

Add a completion note to `.Codex/tasks/current-tasks.md` only if the implementation session is following the local project task checklist. Use a new task entry:

```markdown
- [x] Task 9: Add Research Workflow run skeleton.
  - Verification: `python -m pytest tests/test_research_run_service.py tests/test_research_run_store.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py -q`
  - Completion note: Added ResearchRun schemas, file persistence, knowledge-pack skeleton generation, API routes, and a Streamlit workflow launcher without invoking LLMs or external MCP servers.
```

- [ ] **Step 5: Commit final tracking update if changed**

Run only if `.Codex/tasks/current-tasks.md` was modified:

```powershell
git add .Codex/tasks/current-tasks.md
git commit -m "chore: record research run skeleton task"
```

## Self-Review Checklist

Spec coverage:

- Milestone 1 `ResearchRun` model: Task 1.
- Run store: Task 2.
- Knowledge Pack folder creation: Task 3.
- Trace skeleton: Task 3.
- API routes: Task 5.
- Workflow launcher and monitor: Task 6.
- Verification: Task 7.

Deferred requirements:

- Zotero item processing is deferred to the Milestone 2 plan.
- ResearchAgent MCP Server and external MCP adapters are deferred to the Milestone 3 plan.
- Multi-agent synthesis and full Knowledge Pack generation are deferred to the Milestone 4 plan.

Placeholder scan:

- This plan intentionally avoids `TBD` and `TODO`.
- Every code-changing task includes concrete code.
- Every test task includes exact commands and expected outcomes.

Type consistency:

- `ResearchRunOptions`, `ResearchRunStep`, `ResearchRunArtifact`, `ResearchRun`, `ResearchRunCreateRequest`, and `ResearchRunListResponse` are defined in Task 1 and reused unchanged later.
- Router and service use the same `run_id`, `collection_id`, `collection_name`, `output_dir`, `steps`, and `artifacts` fields.
