"""
Research Pipeline Runner

执行 pipeline 各阶段的调度器。
"""

import traceback
from typing import Any, Callable

from app.research_pipeline import events, store
from app.research_pipeline.agents.planner_wrapper import PlannerAgentWrapper
from app.research_pipeline.agents.reader import ReaderAgent
from app.research_pipeline.agents.retriever import RetrieverAgent
from app.research_pipeline.sources.arxiv import ArxivSourceAdapter
from app.research_pipeline.sources.semantic_scholar import SemanticScholarSourceAdapter
from app.research_pipeline.sources.zotero import ZoteroSourceAdapter


class StubAgent:
    """
    Stub agent for testing pipeline state machine.

    Does not make LLM calls, API requests, or read PDFs.
    Simply simulates stage execution by writing events and updating state.
    """

    def __init__(self, stage: str, db_path: str, run_id: str):
        """
        Initialize stub agent.

        Args:
            stage: Stage name.
            db_path: Path to SQLite database file.
            run_id: Run ID.
        """
        self.stage = stage
        self.db_path = db_path
        self.run_id = run_id

    def execute(self) -> dict[str, Any]:
        """
        Execute stub stage logic.

        Returns:
            Dictionary with stage results.
        """
        # Write start event
        events.write_stage_start_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage=self.stage,
        )

        # Simulate stage-specific work with events
        if self.stage == "planner":
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Analyzing research question",
                payload={"action": "normalize_question"},
            )
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Generating search strategy",
                payload={"action": "generate_plan"},
            )
            result = {"normalized_question": "stub normalized question"}

        elif self.stage == "retriever":
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Searching paper sources",
                payload={"action": "search"},
            )
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Ranking candidates",
                payload={"action": "rank"},
            )
            result = {"candidates_found": 5, "candidates_selected": 3}

        elif self.stage == "reader":
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Reading paper 1/3",
                payload={"action": "extract", "paper_index": 1},
            )
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Reading paper 2/3",
                payload={"action": "extract", "paper_index": 2},
            )
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Reading paper 3/3",
                payload={"action": "extract", "paper_index": 3},
            )
            result = {"papers_read": 3, "cards_created": 3}

        elif self.stage == "synthesis":
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Synthesizing research report",
                payload={"action": "synthesize"},
            )
            result = {"report_sections": 5, "citations": 12}

        elif self.stage == "harness":
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Verifying claims",
                payload={"action": "verify"},
            )
            result = {"claims_verified": 8, "claims_flagged": 2}

        else:
            result = {}

        # Write completion event
        events.write_stage_complete_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage=self.stage,
            payload=result,
        )

        return result


class ReaderAgentWrapper:
    """
    Wrapper for ReaderAgent that implements the execute() interface.

    Integrates with pipeline runner by:
    - Reading the candidate selection plan
    - Filtering candidates based on selected_paper_ids
    - Running batch_read_papers with concurrency control
    - Saving PaperCards to store
    - Writing events for progress tracking
    - Determining stage status based on success/failure counts
    """

    def __init__(self, stage: str, db_path: str, run_id: str):
        """
        Initialize reader agent wrapper.

        Args:
            stage: Stage name (should be "reader").
            db_path: Path to SQLite database file.
            run_id: Run ID.
        """
        self.stage = stage
        self.db_path = db_path
        self.run_id = run_id
        self.reader = ReaderAgent(db_path=db_path)

    def execute(self) -> dict[str, Any]:
        """
        Execute reader stage.

        Returns:
            Dictionary with stage results including cards_created, papers_read, etc.
        """
        # Write start event
        events.write_stage_start_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage=self.stage,
        )

        # Get run details to extract reader_concurrency
        run_detail = store.get_run_detail(self.db_path, self.run_id)
        reader_concurrency = run_detail.get("reader_concurrency", 3)
        reading_focus = run_detail.get("reading_focus")

        # Get the latest candidate_selection plan
        plans = store.get_plans_by_run(self.db_path, self.run_id)
        candidate_plans = [p for p in plans if p["phase"] == "candidate_selection"]

        if not candidate_plans:
            # No selection plan yet - this shouldn't happen in normal flow
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="No candidate selection plan found",
            )
            raise RuntimeError("No candidate selection plan found for run")

        latest_plan = max(candidate_plans, key=lambda p: p["version"])
        selected_paper_ids = latest_plan["plan_data"].get("selected_paper_ids", [])

        if not selected_paper_ids:
            # No papers selected
            events.write_stage_complete_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                payload={"papers_read": 0, "cards_created": 0, "message": "No papers selected"},
            )
            return {"papers_read": 0, "cards_created": 0}

        # Get all candidates and filter by selected_paper_ids
        all_candidates_raw = store.get_candidates(self.db_path, self.run_id)
        # Convert dict to PaperCandidate objects
        from app.research_pipeline.schemas import PaperCandidate

        all_candidates = [PaperCandidate(**c) for c in all_candidates_raw]
        selected_candidates = [
            c for c in all_candidates if c.paper_id in selected_paper_ids
        ]

        events.write_stage_progress_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage=self.stage,
            message=f"Reading {len(selected_candidates)} selected papers",
            payload={"total_papers": len(selected_candidates), "concurrency": reader_concurrency},
        )

        # Read papers in batch with concurrency control
        result = self.reader.batch_read_papers(
            candidates=selected_candidates,
            reading_focus=reading_focus,
            concurrency=reader_concurrency,
        )

        cards = result["cards"]
        summary = result["summary"]

        # Save all cards to store
        for card in cards:
            store.create_paper_card(self.db_path, self.run_id, card)

        # Write events for each card
        for card in cards:
            if card.status == "failed":
                events.write_stage_error_event(
                    db_path=self.db_path,
                    run_id=self.run_id,
                    stage=self.stage,
                    message=f"Failed to read {card.paper_id}: {card.error}",
                    payload={"paper_id": card.paper_id, "error": card.error},
                )
            elif card.status == "degraded":
                events.write_stage_progress_event(
                    db_path=self.db_path,
                    run_id=self.run_id,
                    stage=self.stage,
                    message=f"Read {card.paper_id} with degraded extraction",
                    payload={"paper_id": card.paper_id, "mode": card.extraction_mode},
                )
            else:
                events.write_stage_progress_event(
                    db_path=self.db_path,
                    run_id=self.run_id,
                    stage=self.stage,
                    message=f"Successfully read {card.paper_id}",
                    payload={"paper_id": card.paper_id, "mode": card.extraction_mode},
                )

        # Determine stage status based on success/failure counts
        # Rule: at least one success → completed or degraded
        #       all failed → stage failed (will be handled by exception)
        has_success = summary["successful"] > 0 or summary["degraded"] > 0
        all_failed = summary["failed"] == summary["total"]

        if all_failed:
            # All papers failed - raise exception to fail the stage
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message=f"All {summary['total']} papers failed to read",
                payload=summary,
            )
            raise RuntimeError(f"All {summary['total']} papers failed to read")

        # At least one success - stage completed or degraded
        # If there are failures, mark as degraded; otherwise completed
        stage_status = "degraded" if summary["failed"] > 0 else "completed"

        final_message = (
            f"Read {summary['total']} papers: "
            f"{summary['successful']} successful, "
            f"{summary['degraded']} degraded, "
            f"{summary['failed']} failed"
        )

        events.write_stage_complete_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage=self.stage,
            payload={
                "papers_read": summary["total"],
                "cards_created": len(cards),
                "successful": summary["successful"],
                "degraded": summary["degraded"],
                "failed": summary["failed"],
                "stage_status": stage_status,
            },
        )

        return {
            "papers_read": summary["total"],
            "cards_created": len(cards),
            "successful": summary["successful"],
            "degraded": summary["degraded"],
            "failed": summary["failed"],
            "stage_status": stage_status,
            "message": final_message,
        }


class PipelineRunner:
    """
    Pipeline runner that executes stages in sequence.

    Coordinates stage execution, state transitions, and error handling.
    """

    def __init__(
        self,
        db_path: str,
        agent_factory: Callable[[str, str, str], Any] | None = None,
    ):
        """
        Initialize pipeline runner.

        Args:
            db_path: Path to SQLite database file.
            agent_factory: Optional factory function to create agents.
                          Signature: (stage: str, db_path: str, run_id: str) -> Agent
                          If None, uses StubAgent for all stages.
        """
        self.db_path = db_path
        self.agent_factory = agent_factory or StubAgent
        self.stages = ["planner", "retriever", "reader", "synthesis", "harness"]

    def run(self, run_id: str) -> None:
        """
        Execute all pipeline stages for a run.

        Transitions run status from queued → running → completed (or failed).
        Each stage transitions from queued → running → completed.

        Args:
            run_id: Run ID to execute.

        Raises:
            Exception: If run not found or stage execution fails.
        """
        try:
            # Transition run to running
            store.update_run_status(
                db_path=self.db_path,
                run_id=run_id,
                status="running",
            )

            # Execute stages in sequence
            for stage_name in self.stages:
                self._execute_stage(run_id, stage_name)

            # Mark run as completed
            store.update_run_status(
                db_path=self.db_path,
                run_id=run_id,
                status="completed",
            )

        except Exception as e:
            # Mark run as failed with error details
            error_message = f"{type(e).__name__}: {str(e)}"
            error_trace = traceback.format_exc()

            store.update_run_status(
                db_path=self.db_path,
                run_id=run_id,
                status="failed",
                error=error_message,
            )

            # Write error event
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=run_id,
                stage="runner",
                message=f"Pipeline failed: {error_message}",
                payload={"traceback": error_trace},
            )

            # Re-raise to allow caller to handle
            raise

    def _execute_stage(self, run_id: str, stage_name: str) -> dict[str, Any]:
        """
        Execute a single stage.

        Transitions stage from queued → running → completed.

        Args:
            run_id: Run ID.
            stage_name: Stage name.

        Returns:
            Dictionary with stage results.

        Raises:
            Exception: If stage execution fails.
        """
        try:
            # Transition stage to running
            store.update_stage(
                db_path=self.db_path,
                run_id=run_id,
                stage=stage_name,
                status="running",
                progress=0.0,
                message=f"Executing {stage_name}",
            )

            # Create and execute agent
            agent = self.agent_factory(stage_name, self.db_path, run_id)
            result = agent.execute()

            # Check if agent wants to set specific stage status (e.g., "degraded")
            stage_status = result.get("stage_status", "completed")

            # Mark stage as completed or degraded
            store.update_stage(
                db_path=self.db_path,
                run_id=run_id,
                stage=stage_name,
                status=stage_status,
                progress=1.0,
                message=result.get("message", f"{stage_name.capitalize()} completed successfully"),
            )

            return result

        except Exception as e:
            # Mark stage as failed
            error_message = f"{type(e).__name__}: {str(e)}"

            store.update_stage(
                db_path=self.db_path,
                run_id=run_id,
                stage=stage_name,
                status="failed",
                error=error_message,
            )

            # Write error event
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=run_id,
                stage=stage_name,
                message=f"Stage failed: {error_message}",
            )

            # Re-raise to fail the run
            raise


def create_default_agent(stage: str, db_path: str, run_id: str) -> Any:
    """
    Default agent factory that creates real agents for each stage.

    Args:
        stage: Stage name.
        db_path: Path to SQLite database file.
        run_id: Run ID.

    Returns:
        Agent instance for the given stage.
    """
    if stage == "planner":
        return PlannerAgentWrapper(stage, db_path, run_id)
    elif stage == "retriever":
        # Create retriever agent with real source adapters
        # Note: In production, these would be initialized with proper config
        # For now, we use None and they'll be initialized with defaults
        return RetrieverAgent(
            db_path=db_path,
            run_id=run_id,
            semantic_scholar_adapter=SemanticScholarSourceAdapter(client=None),
            arxiv_adapter=ArxivSourceAdapter(client=None),
            zotero_adapter=ZoteroSourceAdapter(client=None),
        )
    elif stage == "reader":
        return ReaderAgentWrapper(stage, db_path, run_id)
    else:
        # For other stages, use stub agents
        return StubAgent(stage, db_path, run_id)

