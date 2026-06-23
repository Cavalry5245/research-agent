"""
Research Pipeline Router

FastAPI router for research pipeline operations.
Exposes endpoints for creating, listing, getting, and cancelling research runs.
"""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.config import settings
from app.research_pipeline.schemas import (
    ResearchRunCreateRequest,
    ResearchRunCreateResponse,
    ResearchRunDetailResponse,
    ResearchRunListResponse,
    ReportWithClaimsResponse,
)
from app.research_pipeline.service import ResearchPipelineService
from app.research_pipeline.sources.zotero import ZoteroSourceAdapter
from app.research_pipeline.runner import PipelineRunner, create_default_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research-pipeline", tags=["research-pipeline"])

_service_instance: ResearchPipelineService | None = None
_runner_instance: PipelineRunner | None = None


def get_service() -> ResearchPipelineService:
    """
    Get or create the ResearchPipelineService instance.

    Returns:
        ResearchPipelineService singleton instance.
    """
    global _service_instance
    if _service_instance is None:
        from pathlib import Path
        from app.research_pipeline import store

        storage_root = Path(settings.metadata_dir).parent
        db_path = str(storage_root / "research_pipeline.db")

        # Initialize database tables if not exists
        store.init_db(db_path)

        _service_instance = ResearchPipelineService(db_path=db_path)
    return _service_instance


def get_runner(db_path: str) -> PipelineRunner:
    """
    Get or create the PipelineRunner instance.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        PipelineRunner instance.
    """
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = PipelineRunner(
            db_path=db_path,
            agent_factory=create_default_agent,
        )
    return _runner_instance


def schedule_pipeline_run(run_id: str) -> None:
    """
    Schedule a pipeline run to execute in the background.

    Args:
        run_id: Run ID to execute.
    """
    from pathlib import Path

    storage_root = Path(settings.metadata_dir).parent
    db_path = str(storage_root / "research_pipeline.db")

    runner = get_runner(db_path)

    def run_in_background():
        try:
            logger.info(f"Starting background pipeline execution for run_id={run_id}")
            runner.run(run_id)
            logger.info(f"Pipeline execution completed for run_id={run_id}")
        except Exception as e:
            logger.error(f"Pipeline execution failed for run_id={run_id}: {e}", exc_info=True)

    # Start execution in background thread
    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()


@router.post("/runs", response_model=ResearchRunCreateResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    request: ResearchRunCreateRequest,
    service: ResearchPipelineService = Depends(get_service),
) -> ResearchRunCreateResponse:
    """
    Create a new research run.

    Args:
        request: Run creation request with parameters.
        service: ResearchPipelineService dependency.

    Returns:
        ResearchRunCreateResponse with run_id, status, and created_at.

    Raises:
        HTTPException: 400 if validation fails.
    """
    try:
        return service.create_run(request, runner_scheduler=schedule_pipeline_run)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/runs", response_model=ResearchRunListResponse)
def list_runs(
    limit: int = 50,
    service: ResearchPipelineService = Depends(get_service),
) -> ResearchRunListResponse:
    """
    List research runs in reverse chronological order.

    Args:
        limit: Maximum number of runs to return (default 50).
        service: ResearchPipelineService dependency.

    Returns:
        ResearchRunListResponse with count and runs list.
    """
    return service.list_runs(limit=limit)


@router.get("/runs/{run_id}", response_model=ResearchRunDetailResponse)
def get_run_detail(
    run_id: str,
    service: ResearchPipelineService = Depends(get_service),
) -> ResearchRunDetailResponse:
    """
    Get detailed information about a research run.

    Args:
        run_id: Run ID to retrieve.
        service: ResearchPipelineService dependency.

    Returns:
        ResearchRunDetailResponse with full run state.

    Raises:
        HTTPException: 404 if run not found.
    """
    try:
        return service.get_run_detail(run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: str,
    service: ResearchPipelineService = Depends(get_service),
) -> dict:
    """
    Cancel a research run.

    Only queued, running, or degraded runs can be cancelled.
    Completed, failed, or already cancelled runs return 409 conflict.

    Args:
        run_id: Run ID to cancel.
        service: ResearchPipelineService dependency.

    Returns:
        Success message.

    Raises:
        HTTPException: 404 if run not found, 409 if cannot be cancelled.
    """
    try:
        service.cancel_run(run_id)
        return {"message": "Run cancelled successfully"}
    except ValueError as e:
        error_msg = str(e)
        # Distinguish between not found and conflict errors
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            ) from e
        else:
            # Cannot cancel error (wrong status)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            ) from e


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    run_id: str,
    service: ResearchPipelineService = Depends(get_service),
) -> Response:
    """
    Delete a research run and all associated persisted pipeline records.

    Args:
        run_id: Run ID to delete.
        service: ResearchPipelineService dependency.

    Returns:
        Empty 204 response.

    Raises:
        HTTPException: 404 if run not found.
    """
    try:
        service.delete_run(run_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/runs/{run_id}/rerun",
    response_model=ResearchRunCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def rerun_run(
    run_id: str,
    service: ResearchPipelineService = Depends(get_service),
) -> ResearchRunCreateResponse:
    """
    Re-run an existing research run with identical parameters.

    Creates a new run using the same question, source mode, collection key,
    and other settings as the specified run, then starts the pipeline.

    Args:
        run_id: ID of the existing run to replicate.
        service: ResearchPipelineService dependency.

    Returns:
        ResearchRunCreateResponse for the new run.

    Raises:
        HTTPException: 404 if original run not found.
    """
    try:
        return service.rerun_run(run_id, runner_scheduler=schedule_pipeline_run)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/sources/zotero/collections")
def list_zotero_collections(limit: int = 100) -> dict:
    """
    List Zotero collections from local Zotero instance.

    Args:
        limit: Maximum number of collections to return (default 100).

    Returns:
        Dictionary with collections list.

    Raises:
        HTTPException: 503 if Zotero API is unavailable.
    """
    try:
        adapter = ZoteroSourceAdapter()
        collections = adapter.list_collections(limit=limit)
        return {"collections": collections, "count": len(collections)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Zotero API unavailable: {str(e)}",
        ) from e


@router.get("/runs/{run_id}/report", response_model=ReportWithClaimsResponse)
def get_report(
    run_id: str,
    service: ResearchPipelineService = Depends(get_service),
) -> ReportWithClaimsResponse:
    """
    Get report with claims and verification summary.

    Returns JSON response with markdown content, all claims with verification
    status, and aggregated summary counts.

    Args:
        run_id: Run ID to retrieve report for.
        service: ResearchPipelineService dependency.

    Returns:
        ReportWithClaimsResponse with markdown, claims, and summary.

    Raises:
        HTTPException: 404 if report not found.
    """
    try:
        return service.get_report_with_claims(run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/runs/{run_id}/report.md")
def get_report_markdown(
    run_id: str,
    service: ResearchPipelineService = Depends(get_service),
) -> Response:
    """
    Download report as markdown file.

    Returns markdown file with content-disposition header for download.

    Args:
        run_id: Run ID to retrieve report for.
        service: ResearchPipelineService dependency.

    Returns:
        Response with text/markdown content and download headers.

    Raises:
        HTTPException: 404 if report not found.
    """
    try:
        report = service.get_report_with_claims(run_id)
        return Response(
            content=report.markdown,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}_report.md"'
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
