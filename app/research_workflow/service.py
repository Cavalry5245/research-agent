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
    def __init__(
        self,
        store: FileResearchRunStore,
        vault_root: str | Path,
        tool_registry_factory: Callable[[], ToolRegistry] | None = None,
    ) -> None:
        self._store = store
        self._vault_root = Path(vault_root)
        self._tool_registry_factory = tool_registry_factory or build_default_tool_registry

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
        cancelled = self._store.update(run_id, self._cancel_run)
        if cancelled is None:
            raise ResearchRunNotFoundError(run_id)
        return cancelled

    def _cancel_run(self, run: ResearchRun) -> ResearchRun:
        if run.status in {"completed", "failed", "cancelled"}:
            raise ResearchRunConflictError(
                f"Research run {run.run_id} cannot be cancelled from status {run.status}"
            )

        now = datetime.now(timezone.utc)
        steps = [
            step.model_copy(
                update={
                    "status": "cancelled",
                    "completed_at": now,
                    "message": step.message or "Cancelled before execution",
                }
            )
            if step.status in {"queued", "running"}
            else step
            for step in run.steps
        ]
        cancelled = run.model_copy(
            update={
                "status": "cancelled",
                "progress": 0.0,
                "steps": steps,
                "completed_at": now,
                "updated_at": now,
                "error": "Research run cancelled",
            }
        )
        return create_knowledge_pack_skeleton(cancelled, self._vault_root)

    def _new_run_id(self, now: datetime) -> str:
        return f"run_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
