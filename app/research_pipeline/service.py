"""
Research Pipeline Service

核心业务逻辑层，协调各模块完成研究任务。
"""

from datetime import datetime
from typing import Callable

from app.research_pipeline import store
from app.research_pipeline.schemas import (
    ResearchRunCreateRequest,
    ResearchRunCreateResponse,
    ResearchRunDetailResponse,
    ResearchRunListResponse,
    ResearchRunSummary,
    ResearchStage,
    ResearchEvent,
    PaperCandidate,
    PaperCard,
    ReportClaim,
    ReportWithClaimsResponse,
)


class ResearchPipelineService:
    """
    Research Pipeline Service Layer

    Sits between FastAPI routes and store, handling business logic,
    validation, and response assembly.
    """

    def __init__(self, db_path: str):
        """
        Initialize service with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path

    def create_run(
        self,
        request: ResearchRunCreateRequest,
        runner_scheduler: Callable[[str], None] | None = None,
    ) -> ResearchRunCreateResponse:
        """
        Create a new research run with validation.

        Args:
            request: Run creation request with parameters.
            runner_scheduler: Optional function to schedule background runner.
                             Called with run_id after creation. Allows testing
                             without starting real background tasks.

        Returns:
            ResearchRunCreateResponse with run_id, status, and created_at.

        Raises:
            ValueError: If validation fails.
        """
        # Validate parameters
        if not request.question or not request.question.strip():
            raise ValueError("question cannot be empty")

        if request.max_reader_papers < 3 or request.max_reader_papers > 15:
            raise ValueError("max_reader_papers must be between 3 and 15")

        if request.reader_concurrency < 1:
            raise ValueError("reader_concurrency must be >= 1")

        if request.source_mode == "zotero_only" and not request.zotero_collection_key:
            raise ValueError(
                "zotero_collection_key required when source_mode is zotero_only"
            )

        # Create run in store
        run_id = store.create_run(
            db_path=self.db_path,
            question=request.question,
            source_mode=request.source_mode,
            max_reader_papers=request.max_reader_papers,
            reader_concurrency=request.reader_concurrency,
            zotero_collection_key=request.zotero_collection_key,
            year_start=request.year_start,
            year_end=request.year_end,
            venue_filter=request.venue_filter,
            keywords=request.keywords,
        )

        # Schedule runner if provided
        if runner_scheduler is not None:
            runner_scheduler(run_id)

        # Get created run details to return
        detail = store.get_run_detail(self.db_path, run_id)

        return ResearchRunCreateResponse(
            run_id=run_id,
            status=detail["status"],
            created_at=datetime.fromisoformat(detail["created_at"]),
        )

    def list_runs(self, limit: int = 50) -> ResearchRunListResponse:
        """
        List runs in reverse chronological order.

        Args:
            limit: Maximum number of runs to return (default 50).

        Returns:
            ResearchRunListResponse with count and runs list.
        """
        runs = store.list_runs(db_path=self.db_path, limit=limit)

        return ResearchRunListResponse(
            count=len(runs),
            runs=[
                ResearchRunSummary(
                    run_id=run["run_id"],
                    question=run["question"],
                    source_mode=run["source_mode"],
                    status=run["status"],
                    error=run["error"],
                    created_at=datetime.fromisoformat(run["created_at"]),
                )
                for run in runs
            ],
        )

    def get_run_detail(self, run_id: str) -> ResearchRunDetailResponse:
        """
        Get detailed run information with frontend-ready response structure.

        Returns stages, events, candidates, cards, plan, and report summary.
        Candidates are populated from store; cards/plan/report remain empty for MVP.

        Args:
            run_id: Run ID to retrieve.

        Returns:
            ResearchRunDetailResponse with full run state.

        Raises:
            ValueError: If run not found (404).
        """
        detail = store.get_run_detail(self.db_path, run_id)

        if detail is None:
            raise ValueError(f"Run {run_id} not found")

        # Parse stages
        stages = [
            ResearchStage(
                id=stage["id"],
                run_id=stage["run_id"],
                stage=stage["stage"],
                status=stage["status"],
                progress=stage["progress"],
                message=stage["message"],
                started_at=(
                    datetime.fromisoformat(stage["started_at"])
                    if stage["started_at"]
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(stage["completed_at"])
                    if stage["completed_at"]
                    else None
                ),
                error=stage["error"],
                created_at=datetime.utcnow(),  # Not stored in store, use current time
            )
            for stage in detail["stages"]
        ]

        # Parse events
        events = [
            ResearchEvent(
                id=event["id"],
                run_id=event["run_id"],
                stage=event["stage"],
                level=event["level"],
                message=event["message"],
                payload=event["payload"],
                created_at=datetime.fromisoformat(event["created_at"]),
            )
            for event in detail["events"]
        ]

        # Parse candidates
        candidates = [
            PaperCandidate(
                paper_id=c["paper_id"],
                source=c["source"],
                title=c["title"],
                authors=c["authors"],
                year=c["year"],
                venue=c["venue"],
                abstract=c["abstract"],
                doi=c["doi"],
                arxiv_id=c["arxiv_id"],
                semantic_scholar_id=c["semantic_scholar_id"],
                zotero_item_id=c["zotero_item_id"],
                url=c["url"],
                pdf_url=c["pdf_url"],
                local_pdf_path=c["local_pdf_path"],
                citation_count=c["citation_count"],
                relevance_score=c["relevance_score"],
                metadata=c["metadata"],
            )
            for c in detail["candidates"]
        ]

        # Parse paper cards
        cards = [
            PaperCard(
                paper_id=card["paper_id"],
                status=card["status"],
                extraction_mode=card["extraction_mode"],
                title=card["title"],
                bibliographic_metadata=card["bibliographic_metadata"],
                research_problem=card["research_problem"],
                method=card["method"],
                datasets=card["datasets"],
                metrics=card["metrics"],
                key_results=card["key_results"],
                limitations=card["limitations"],
                assumptions=card["assumptions"],
                future_work=card["future_work"],
                claims=card["claims"],
                evidence=card["evidence"],
                error=card["error"],
            )
            for card in detail.get("cards", [])
        ]

        return ResearchRunDetailResponse(
            run_id=detail["run_id"],
            question=detail["question"],
            normalized_question=detail["normalized_question"],
            source_mode=detail["source_mode"],
            zotero_collection_key=detail["zotero_collection_key"],
            status=detail["status"],
            max_reader_papers=detail["max_reader_papers"],
            reader_concurrency=detail["reader_concurrency"],
            year_start=detail["year_start"],
            year_end=detail["year_end"],
            venue_filter=detail["venue_filter"],
            keywords=detail["keywords"],
            created_at=datetime.fromisoformat(detail["created_at"]),
            started_at=(
                datetime.fromisoformat(detail["started_at"])
                if detail["started_at"]
                else None
            ),
            completed_at=(
                datetime.fromisoformat(detail["completed_at"])
                if detail["completed_at"]
                else None
            ),
            failed_at=(
                datetime.fromisoformat(detail["failed_at"])
                if detail["failed_at"]
                else None
            ),
            cancelled_at=(
                datetime.fromisoformat(detail["cancelled_at"])
                if detail["cancelled_at"]
                else None
            ),
            error=detail["error"],
            stages=stages,
            events=events,
            candidates=candidates,
            cards=cards,
            plan=None,  # No plan yet for MVP
            report=None,  # No report yet for MVP
        )

    def cancel_run(self, run_id: str) -> None:
        """
        Cancel a research run.

        Only queued, running, or degraded runs can be cancelled.
        Completed, failed, or already cancelled runs return a conflict error.

        Args:
            run_id: Run ID to cancel.

        Raises:
            ValueError: If run not found (404) or cannot be cancelled (409 conflict).
        """
        # Get current run state
        detail = store.get_run_detail(self.db_path, run_id)

        if detail is None:
            raise ValueError(f"Run {run_id} not found")

        current_status = detail["status"]

        # Check if cancellation is allowed
        allowed_statuses = {"queued", "running", "degraded"}

        if current_status not in allowed_statuses:
            raise ValueError(
                f"Cannot cancel run with status {current_status}. "
                f"Only queued, running, or degraded runs can be cancelled."
            )

        # Update status to cancelled
        store.update_run_status(
            db_path=self.db_path,
            run_id=run_id,
            status="cancelled",
        )

    def get_report_with_claims(self, run_id: str) -> ReportWithClaimsResponse:
        """
        Get report with claims and verification summary.

        Assembles the complete report response including markdown content,
        all claims with their verification status, and aggregated summary counts.

        Args:
            run_id: Run ID to retrieve report for.

        Returns:
            ReportWithClaimsResponse with markdown, claims list, and summary dict.

        Raises:
            ValueError: If report not found (404).
        """
        # Get report
        report = store.get_report(self.db_path, run_id)

        if report is None:
            raise ValueError(f"Report not found for run {run_id}")

        # Get claims
        claims_data = store.get_claims(self.db_path, run_id)

        # Parse claims into schema
        claims = [
            ReportClaim(
                claim_text=c["claim_text"],
                claim_type=c["claim_type"],
                citation_ids=c["citation_ids"],
                evidence_ids=c["evidence_ids"],
                verification_status=c["verification_status"],
                verification_reason=c["verification_reason"],
            )
            for c in claims_data
        ]

        # Get summary
        summary = store.get_claim_summary(self.db_path, run_id)

        return ReportWithClaimsResponse(
            markdown=report["markdown"],
            claims=claims,
            summary=summary,
        )

