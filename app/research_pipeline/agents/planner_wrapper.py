"""
Planner Agent Wrapper for Pipeline Integration

提供PlannerAgent的pipeline集成wrapper，实现execute()接口。
"""

import logging
from typing import Any

from app.research_pipeline import store, events
from app.research_pipeline.agents.planner import PlannerAgent


logger = logging.getLogger(__name__)


class PlannerAgentWrapper:
    """
    Wrapper for PlannerAgent to integrate with PipelineRunner.

    Executes both initial planning and candidate selection phases.
    """

    def __init__(self, stage: str, db_path: str, run_id: str):
        """
        Initialize planner wrapper.

        Args:
            stage: Stage name (should be "planner")
            db_path: Path to SQLite database
            run_id: Research run ID
        """
        self.stage = stage
        self.db_path = db_path
        self.run_id = run_id
        self.agent = PlannerAgent(db_path=db_path)

    async def execute(self) -> dict[str, Any]:
        """
        Execute planner stage: initial planning + candidate selection.

        Returns:
            Summary dict with stage_status, message, and plan info.

        Raises:
            RuntimeError: If both planning phases fail.
        """
        # Get run details for question and parameters
        run_detail = store.get_run_detail(self.db_path, self.run_id)
        question = run_detail["question"]
        source_mode = run_detail["source_mode"]
        max_reader_papers = run_detail["max_reader_papers"]

        # Phase 1: Initial planning
        events.write_stage_progress_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage=self.stage,
            message="Generating initial research plan",
        )

        try:
            initial_plan = self.agent.plan_initial(question, source_mode)

            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message="Initial plan generated",
                payload={
                    "phase": "initial",
                    "fallback_used": initial_plan.plan_data.get("fallback_used", False),
                    "queries": initial_plan.plan_data.get("queries", []),
                },
            )
        except Exception as e:
            error_msg = f"Initial planning failed: {type(e).__name__}: {str(e)}"
            logger.error(error_msg)
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message=error_msg,
            )
            raise RuntimeError(error_msg) from e

        # Phase 2: Candidate selection (only after retriever completes)
        # Check if we have candidates
        candidates = store.get_candidates(self.db_path, self.run_id)

        if not candidates:
            # No candidates yet - planner can only complete initial phase
            return {
                "stage_status": "completed",
                "message": "Initial plan completed, awaiting retriever results",
                "initial_plan_version": initial_plan.version,
                "candidates_available": False,
            }

        # We have candidates - proceed with selection
        events.write_stage_progress_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage=self.stage,
            message=f"Selecting papers from {len(candidates)} candidates",
        )

        try:
            selection_plan = self.agent.plan_candidate_selection(
                run_id=self.run_id,
                max_reader_papers=max_reader_papers,
            )

            selected_count = len(selection_plan.plan_data.get("selected_paper_ids", []))

            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message=f"Selected {selected_count} papers for reading",
                payload={
                    "phase": "candidate_selection",
                    "fallback_used": selection_plan.plan_data.get("fallback_used", False),
                    "selected_count": selected_count,
                    "total_candidates": len(candidates),
                },
            )

            return {
                "stage_status": "completed",
                "message": f"Planning complete: selected {selected_count}/{len(candidates)} papers",
                "initial_plan_version": initial_plan.version,
                "selection_plan_version": selection_plan.version,
                "selected_count": selected_count,
                "candidates_available": True,
            }

        except Exception as e:
            error_msg = f"Candidate selection failed: {type(e).__name__}: {str(e)}"
            logger.error(error_msg)
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage=self.stage,
                message=error_msg,
            )

            # Selection failure is degraded, not fatal (initial plan succeeded)
            return {
                "stage_status": "degraded",
                "message": "Initial plan succeeded, candidate selection failed",
                "initial_plan_version": initial_plan.version,
                "error": error_msg,
            }
