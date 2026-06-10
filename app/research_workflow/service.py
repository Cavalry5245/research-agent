from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.research_workflow.knowledge_pack import (
    append_tool_call_record,
    create_knowledge_pack_skeleton,
    update_knowledge_pack_run_files,
)
from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.schemas import (
    ResearchRun,
    ResearchRunCreateRequest,
    build_default_steps,
)
from app.research_workflow.store import FileResearchRunStore
from app.research_workflow.zotero_intake import (
    CollectionIntakeService,
    ZoteroLocalHttpClient,
)


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

    def execute_local_run(
        self,
        run_id: str,
        intake_service: CollectionIntakeService | None = None,
        paper_processor: PaperProcessingService | None = None,
    ) -> ResearchRun:
        run = self.get_run(run_id)
        if run.status in {"completed", "failed", "cancelled"}:
            raise ResearchRunConflictError(
                f"Research run {run.run_id} cannot be executed from status {run.status}"
            )

        now = datetime.now(timezone.utc)
        run = create_knowledge_pack_skeleton(
            run.model_copy(
                update={
                    "status": "running",
                    "started_at": run.started_at or now,
                    "updated_at": now,
                }
            ),
            self._vault_root,
        )
        run = self._mark_step(
            run, "collection_intake", "running", 0.0, "Reading Zotero collection"
        )
        self._store.upsert(run)
        update_knowledge_pack_run_files(run)

        intake_service = intake_service or CollectionIntakeService(ZoteroLocalHttpClient())
        paper_processor = paper_processor or self._default_paper_processor()

        items = intake_service.collect_items(run.collection_id, run.options.max_papers)
        append_tool_call_record(
            run,
            {
                "tool_name": "zotero.list_collection_items",
                "provider": "local_http",
                "status": "completed",
                "result_summary": f"{len(items)} item(s)",
            },
        )
        run = run.model_copy(
            update={"paper_items": items, "updated_at": datetime.now(timezone.utc)}
        )
        run = self._mark_step(
            run,
            "collection_intake",
            "completed",
            1.0,
            f"Collected {len(items)} item(s)",
        )
        run = self._mark_step(
            run, "paper_understanding", "running", 0.0, "Processing local papers"
        )
        self._store.upsert(run)
        update_knowledge_pack_run_files(run)

        processed_items = []
        for index, item in enumerate(items, start=1):
            if item.status != "queued":
                processed_items.append(item)
            else:
                result = paper_processor.process_item(item, run.output_dir)
                processed_items.append(result.item)
                append_tool_call_record(
                    run,
                    {
                        "tool_name": "research_agent.process_paper",
                        "provider": "local_service",
                        "status": result.item.status,
                        "arguments": {"zotero_item_id": item.zotero_item_id},
                        "result_summary": result.item.paper_id or result.item.error or "",
                    },
                )
            progress = index / max(len(items), 1)
            run = run.model_copy(
                update={
                    "paper_items": processed_items + items[index:],
                    "progress": round(progress, 3),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._store.upsert(run)
            update_knowledge_pack_run_files(run)

        completed_count = sum(
            1 for item in processed_items if item.status == "completed"
        )
        failed_count = sum(1 for item in processed_items if item.status == "failed")
        skipped_count = sum(1 for item in processed_items if item.status == "skipped")
        final_status = (
            "completed" if completed_count or skipped_count or not failed_count else "failed"
        )
        completed_at = datetime.now(timezone.utc)
        run = run.model_copy(
            update={
                "status": final_status,
                "progress": 1.0,
                "paper_items": processed_items,
                "updated_at": completed_at,
                "completed_at": completed_at,
                "error": None if final_status == "completed" else "All paper items failed",
            }
        )
        understanding_status = (
            "completed" if completed_count or skipped_count or not processed_items else "failed"
        )
        run = self._mark_step(
            run,
            "paper_understanding",
            understanding_status,
            1.0,
            f"Completed={completed_count}, failed={failed_count}, skipped={skipped_count}",
        )
        self._store.upsert(run)
        update_knowledge_pack_run_files(run)
        return run

    def cancel_run(self, run_id: str) -> ResearchRun:
        cancelled = self._store.update(run_id, self._cancel_run)
        if cancelled is None:
            raise ResearchRunNotFoundError(run_id)
        return cancelled

    def _default_paper_processor(self) -> PaperProcessingService:
        from app.config import settings
        from app.services.embedding_client import EmbeddingClient
        from app.services.vector_store import VectorStore

        return PaperProcessingService(
            upload_dir=settings.upload_dir,
            metadata_dir=settings.metadata_dir,
            note_dir=settings.note_dir,
            vector_store=VectorStore(),
            embedding_client=EmbeddingClient(),
        )

    def _mark_step(
        self,
        run: ResearchRun,
        step_id: str,
        status: str,
        progress: float,
        message: str,
    ) -> ResearchRun:
        now = datetime.now(timezone.utc)
        steps = []
        for step in run.steps:
            if step.step_id != step_id:
                steps.append(step)
                continue
            update = {
                "status": status,
                "progress": progress,
                "message": message,
            }
            if status == "running" and step.started_at is None:
                update["started_at"] = now
            if status in {"completed", "failed", "cancelled"}:
                update["completed_at"] = now
            steps.append(step.model_copy(update=update))
        return run.model_copy(update={"steps": steps, "updated_at": now})

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
