from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.mcp.client_manager import MCPClientManager
from app.mcp.installer import ensure_zotero_mcp_installed
from app.mcp.schemas import MCPServerConfig
from app.research_workflow.knowledge_pack import (
    create_knowledge_pack_skeleton,
    update_knowledge_pack_run_files,
    write_synthesis_files,
)
from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.schemas import (
    ResearchRun,
    ResearchRunCreateRequest,
    ResearchRunPaperItem,
    build_default_steps,
)
from app.research_workflow.store import FileResearchRunStore
from app.research_workflow.synthesis import (
    KnowledgePackSynthesisService,
    SynthesisResult,
)
from app.research_workflow.tool_adapters import ObsidianAdapter
from app.research_workflow.tool_registry import (
    ToolDefinition,
    ToolRegistry,
    build_default_tool_registry,
)
from app.research_workflow.zotero_intake import (
    CollectionIntakeService,
    ZoteroLocalHttpClient,
)

logger = logging.getLogger(__name__)


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
        mcp_manager: MCPClientManager | None = None,
    ) -> None:
        self._store = store
        self._vault_root = Path(vault_root)
        self._tool_registry_factory = tool_registry_factory or build_default_tool_registry
        self._mcp_manager = mcp_manager if mcp_manager is not None else self._init_mcp_manager()

    def _init_mcp_manager(self) -> MCPClientManager | None:
        """Initialize MCP manager and start configured servers."""
        if not settings.mcp_enabled:
            return None

        manager = MCPClientManager()

        # Start Zotero MCP server if enabled
        if settings.zotero_mcp_enabled:
            if settings.zotero_mcp_auto_install:
                success, error = ensure_zotero_mcp_installed()
                if not success:
                    logger.warning(f"Failed to install Zotero MCP: {error}")
                    return manager

            try:
                config = MCPServerConfig(
                    name="zotero",
                    command=["zotero-mcp"],
                    env={"ZOTERO_DATA_DIR": settings.zotero_data_dir} if settings.zotero_data_dir else {}
                )
                manager.start_server(config)
                logger.info("Zotero MCP server started")
            except Exception as e:
                logger.warning(f"Failed to start Zotero MCP server: {e}")

        return manager

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

        try:
            intake_service = intake_service or CollectionIntakeService(
                ZoteroLocalHttpClient()
            )
            paper_processor = paper_processor or self._default_paper_processor()
        except Exception as exc:
            return self._fail_run(run, "collection_intake", exc)

        tool_registry = self._tool_registry_factory()
        self._register_intake_tool(tool_registry, intake_service)
        intake_result = tool_registry.dispatch(
            "zotero.list_collection_items",
            {
                "collection_id": run.collection_id,
                "max_papers": run.options.max_papers,
            },
            run=run,
        )
        if intake_result.status == "failed":
            return self._fail_run(
                run,
                "collection_intake",
                RuntimeError(intake_result.error or "Zotero collection intake failed"),
            )

        items = list(intake_result.result or [])
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

        self._register_paper_processing_tool(tool_registry, paper_processor, items)
        processed_items = []
        for index, item in enumerate(items, start=1):
            if item.status != "queued":
                processed_items.append(item)
            else:
                result = tool_registry.dispatch(
                    "research_agent.process_paper",
                    {
                        "zotero_item_id": item.zotero_item_id,
                        "run_output_dir": run.output_dir,
                    },
                    run=run,
                )
                processed_item = self._paper_item_from_tool_result(item, result)
                processed_items.append(processed_item)
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
        if completed_count:
            run = self._generate_knowledge_pack_outputs(run, tool_registry)
        self._store.upsert(run)
        update_knowledge_pack_run_files(run)
        return run

    def _generate_knowledge_pack_outputs(
        self,
        run: ResearchRun,
        tool_registry: ToolRegistry,
    ) -> ResearchRun:
        run = self._mark_step(
            run,
            "literature_synthesis",
            "running",
            0.0,
            "Generating Knowledge Pack synthesis",
        )
        self._register_synthesis_tool(tool_registry, run)
        synthesis_result = tool_registry.dispatch(
            "research_agent.generate_knowledge_pack",
            arguments={"run_id": run.run_id},
            run=run,
        )
        if synthesis_result.status == "failed":
            return self._fail_run(
                run,
                "literature_synthesis",
                RuntimeError(
                    synthesis_result.error or "Knowledge Pack synthesis failed"
                ),
            )

        payload = synthesis_result.result
        run = payload["run"]
        result = payload["result"]
        run = self._mark_step(
            run,
            "literature_synthesis",
            "completed",
            1.0,
            f"Generated {len(result.files)} synthesis file(s)",
        )
        run = self._mark_step(
            run,
            "experiment_planning",
            "completed",
            1.0,
            "Generated actionable experiment plan",
        )

        run = self._mark_step(
            run,
            "obsidian_publishing",
            "running",
            0.0,
            "Publishing Knowledge Pack outputs",
        )
        self._register_obsidian_publish_tool(tool_registry, run, result)
        publish_result = tool_registry.dispatch(
            "obsidian.publish_knowledge_pack",
            {"run_id": run.run_id, "output_dir": run.output_dir},
            run=run,
        )
        if publish_result.status == "failed":
            return self._fail_run(
                run,
                "obsidian_publishing",
                RuntimeError(
                    publish_result.error or "Knowledge Pack publishing failed"
                ),
            )

        published_count = int(publish_result.result["published_count"])
        return self._mark_step(
            run,
            "obsidian_publishing",
            "completed",
            1.0,
            "Knowledge Pack is available as Markdown outputs",
        )

    def _register_intake_tool(
        self,
        registry: ToolRegistry,
        intake_service: CollectionIntakeService,
    ) -> None:
        registry.register(
            ToolDefinition(
                name="zotero.list_collection_items",
                provider="local_http",
                handler=lambda arguments: intake_service.collect_items(
                    str(arguments["collection_id"]),
                    int(arguments["max_papers"]),
                ),
                required_args=("collection_id", "max_papers"),
                fallback_available=True,
                fallback_active=True,
            )
        )

    def _register_paper_processing_tool(
        self,
        registry: ToolRegistry,
        paper_processor: PaperProcessingService,
        items: list[ResearchRunPaperItem],
    ) -> None:
        items_by_zotero_id = {item.zotero_item_id: item for item in items}

        def process(arguments):
            zotero_item_id = str(arguments["zotero_item_id"])
            item = items_by_zotero_id.get(zotero_item_id)
            if item is None:
                raise ValueError(f"Unknown Zotero item: {zotero_item_id}")
            result = paper_processor.process_item(
                item,
                str(arguments["run_output_dir"]),
            )
            return {
                "item": result.item,
                "chunk_count": result.chunk_count,
                "note_path": result.note_path,
                "vector_backend": result.vector_backend,
                "summary": result.item.paper_id or result.item.error or "",
            }

        registry.register(
            ToolDefinition(
                name="research_agent.process_paper",
                provider="local_service",
                handler=process,
                required_args=("zotero_item_id", "run_output_dir"),
            )
        )

    def _register_synthesis_tool(
        self,
        registry: ToolRegistry,
        run: ResearchRun,
    ) -> None:
        def generate(_arguments):
            result = KnowledgePackSynthesisService().generate(run)
            updated_run = write_synthesis_files(run, result)
            return {
                "run": updated_run,
                "result": result,
                "file_count": len(result.files),
                "summary": f"{len(result.files)} file(s)",
            }

        registry.register(
            ToolDefinition(
                name="research_agent.generate_knowledge_pack",
                provider="local_synthesis",
                handler=generate,
                required_args=("run_id",),
            )
        )

    def _register_obsidian_publish_tool(
        self,
        registry: ToolRegistry,
        run: ResearchRun,
        result: SynthesisResult,
    ) -> None:
        def publish(_arguments):
            published_count = self._publish_obsidian_outputs(run, result)
            return {
                "published_count": published_count,
                "summary": f"{published_count} file(s)",
            }

        registry.register(
            ToolDefinition(
                name="obsidian.publish_knowledge_pack",
                provider="direct_markdown",
                handler=publish,
                required_args=("run_id", "output_dir"),
                fallback_available=True,
                fallback_active=True,
            )
        )

    def _paper_item_from_tool_result(
        self,
        item: ResearchRunPaperItem,
        result,
    ) -> ResearchRunPaperItem:
        if result.status == "failed":
            return self._failed_paper_item(
                item,
                RuntimeError(result.error or "Paper processing failed"),
            )
        payload = result.result or {}
        processed_item = payload.get("item") if isinstance(payload, dict) else None
        if isinstance(processed_item, ResearchRunPaperItem):
            return processed_item
        return self._failed_paper_item(
            item,
            RuntimeError("Paper processing returned an invalid result"),
        )

    def _publish_obsidian_outputs(
        self,
        run: ResearchRun,
        result,
    ) -> int:
        if not (run.options.obsidian_publish and run.options.obsidian_vault_path):
            return len(result.files)

        adapter = ObsidianAdapter(run.options.obsidian_vault_path)
        for file in result.files:
            adapter.publish_markdown(
                f"ResearchAgent/Runs/{run.run_id}/{file.filename}",
                file.content,
            )
        return len(result.files)

    def _fail_run(
        self,
        run: ResearchRun,
        step_id: str,
        error: Exception,
    ) -> ResearchRun:
        error_text = str(error)
        completed_at = datetime.now(timezone.utc)
        failed = run.model_copy(
            update={
                "status": "failed",
                "progress": 1.0,
                "updated_at": completed_at,
                "completed_at": completed_at,
                "error": error_text,
            }
        )
        failed = self._mark_step(
            failed,
            step_id,
            "failed",
            1.0,
            error_text,
            error=error_text,
        )
        self._store.upsert(failed)
        update_knowledge_pack_run_files(failed)
        return failed

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
        error: str | None = None,
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
            if error is not None:
                update["error"] = error
            steps.append(step.model_copy(update=update))
        return run.model_copy(update={"steps": steps, "updated_at": now})

    def _failed_paper_item(
        self,
        item: ResearchRunPaperItem,
        error: Exception,
    ) -> ResearchRunPaperItem:
        now = datetime.now(timezone.utc)
        return item.model_copy(
            update={
                "status": "failed",
                "progress": 1.0,
                "error": str(error),
                "started_at": item.started_at or now,
                "updated_at": now,
                "completed_at": now,
            }
        )

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
