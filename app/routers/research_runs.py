from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.research_workflow.paper_processing import PaperProcessingService
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
from app.research_workflow.zotero_intake import (
    CollectionIntakeService,
    ZoteroLocalHttpClient,
)

router = APIRouter(prefix="/research-runs", tags=["research-runs"])

_service_instance: ResearchRunService | None = None


def get_research_run_service() -> ResearchRunService:
    from app.config import settings

    global _service_instance
    if _service_instance is None:
        storage_root = Path(settings.metadata_dir).parent
        store = FileResearchRunStore(storage_root / "research_runs.json")
        vault_root = storage_root / "knowledge_packs"
        _service_instance = ResearchRunService(store=store, vault_root=vault_root)
    return _service_instance


def get_collection_intake_service() -> CollectionIntakeService:
    return CollectionIntakeService(ZoteroLocalHttpClient())


def get_paper_processing_service() -> PaperProcessingService:
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


@router.post("", response_model=ResearchRun, status_code=status.HTTP_201_CREATED)
def create_research_run(
    request: ResearchRunCreateRequest,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    return service.create_run(request)


@router.get("", response_model=ResearchRunListResponse)
def list_research_runs(
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRunListResponse:
    runs = service.list_runs()
    return ResearchRunListResponse(count=len(runs), runs=runs)


@router.post("/{run_id}/execute-local", response_model=ResearchRun)
def execute_research_run_local(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
    intake_service: CollectionIntakeService = Depends(get_collection_intake_service),
    paper_processing_service: PaperProcessingService = Depends(
        get_paper_processing_service
    ),
) -> ResearchRun:
    try:
        return service.execute_local_run(
            run_id,
            intake_service=intake_service,
            paper_processor=paper_processing_service,
        )
    except ResearchRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run {run_id} not found",
        ) from exc
    except ResearchRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/{run_id}", response_model=ResearchRun)
def get_research_run(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.get_run(run_id)
    except ResearchRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run {run_id} not found",
        ) from exc


@router.delete("/{run_id}", response_model=ResearchRun)
def cancel_research_run(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.cancel_run(run_id)
    except ResearchRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run {run_id} not found",
        ) from exc
    except ResearchRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
