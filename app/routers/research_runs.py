from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.research_workflow.mcp_server import (
    MCPToolRequest,
    MCPToolResponse,
    ResearchAgentMCPServer,
)
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
from app.research_workflow.tool_adapters import (
    ArxivAdapter,
    ObsidianAdapter,
    SemanticScholarAdapter,
    ZoteroAdapter,
)
from app.research_workflow.tool_registry import build_default_tool_registry
from app.research_workflow.zotero_intake import (
    CollectionIntakeService,
    ZoteroLocalHttpClient,
)
from app.services.paper_compare import compare_papers
from app.services.paper_qa import answer_question

router = APIRouter(prefix="/research-runs", tags=["research-runs"])

_service_instance: ResearchRunService | None = None
_vector_store_instance: Any | None = None
_embedding_client_instance: Any | None = None
_llm_client_instance: Any | None = None
_reranker_instance: Any | None = None
_retriever_instance: Any | None = None
_bm25_retriever_instance: Any | None = None


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


def get_paper_processing_service() -> PaperProcessingService | None:
    return None


def get_vector_store() -> Any:
    from app.services.vector_store import VectorStore

    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance


def get_embedding_client() -> Any:
    from app.services.embedding_client import EmbeddingClient

    global _embedding_client_instance
    if _embedding_client_instance is None:
        _embedding_client_instance = EmbeddingClient()
    return _embedding_client_instance


def get_llm_client() -> Any:
    from app.services.llm_client import LLMClient

    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance


def get_reranker() -> Any | None:
    from app.config import settings

    global _reranker_instance
    if not settings.enable_rerank:
        return None
    if _reranker_instance is None:
        from app.services.reranker import CrossEncoderReranker

        _reranker_instance = CrossEncoderReranker(model_name=settings.rerank_model)
    return _reranker_instance


def get_retriever() -> Any | None:
    from app.config import settings

    global _bm25_retriever_instance, _retriever_instance
    if settings.retriever == "vector":
        return None
    if settings.retriever == "bm25":
        if _bm25_retriever_instance is None:
            from app.services.bm25_retriever import BM25Retriever

            _bm25_retriever_instance = BM25Retriever(get_vector_store())
        return _bm25_retriever_instance
    if settings.retriever == "hybrid":
        if _retriever_instance is None:
            from app.services.bm25_retriever import BM25Retriever
            from app.services.hybrid_retriever import HybridRetriever

            bm25 = _bm25_retriever_instance or BM25Retriever(get_vector_store())
            _bm25_retriever_instance = bm25
            _retriever_instance = HybridRetriever(
                vector_store=get_vector_store(),
                embedding_client=get_embedding_client(),
                bm25_retriever=bm25,
                alpha=settings.hybrid_alpha,
                recall_top_k=settings.hybrid_recall_top_k,
            )
        return _retriever_instance
    return None


def get_research_agent_mcp_server(
    service: ResearchRunService = Depends(get_research_run_service),
    vector_store: Any = Depends(get_vector_store),
    embedding_client: Any = Depends(get_embedding_client),
    llm_client: Any = Depends(get_llm_client),
    reranker: Any | None = Depends(get_reranker),
    retriever: Any | None = Depends(get_retriever),
) -> ResearchAgentMCPServer:
    from app.config import settings

    def search_backend(
        query: str,
        top_k: int,
        paper_id: str | None = None,
    ) -> Any:
        if retriever is not None:
            return retriever.search(query=query, top_k=top_k, paper_id=paper_id)
        query_embedding = embedding_client.embed_query(query)
        return vector_store.query(
            query_embedding,
            top_k=top_k,
            paper_id=paper_id,
            hybrid_query_text=query,
        )

    def qa_backend(
        question: str,
        run_id: str | None = None,
        paper_id: str | None = None,
        top_k: int = 5,
    ) -> Any:
        del run_id
        result = answer_question(
            question=question,
            vector_store=vector_store,
            embedding_client=embedding_client,
            llm_client=llm_client,
            paper_id=paper_id,
            top_k=settings.rerank_top_k if reranker else top_k,
            reranker=reranker,
            recall_top_k=settings.rerank_recall_top_k if reranker else None,
            retriever=retriever,
        )
        return _jsonable(result)

    def compare_backend(paper_ids: list[str]) -> Any:
        result = compare_papers(
            paper_ids,
            settings.metadata_dir,
            llm_client=llm_client,
        )
        return _jsonable(result)

    return ResearchAgentMCPServer(
        service=service,
        vector_search=search_backend,
        answer_question=qa_backend,
        compare_papers=compare_backend,
    )


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


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


@router.get("/tools/health")
def get_research_run_tools_health() -> dict[str, object]:
    from app.config import settings

    storage_root = Path(settings.metadata_dir).parent
    tools = [
        health.model_dump(mode="json")
        for health in build_default_tool_registry().health()
    ]
    tools.extend(
        health.model_dump(mode="json")
        for health in (
            ZoteroAdapter().health(),
            ObsidianAdapter(storage_root / "knowledge_packs").health(),
            SemanticScholarAdapter(available=False).health(),
            ArxivAdapter(available=False).health(),
        )
    )
    tools.append(
        {
            "tool_name": "ResearchAgent MCP Server",
            "provider": "in_process",
            "available": True,
            "fallback_available": False,
            "fallback_active": False,
            "message": "ResearchAgent MCP Server facade is available",
        }
    )
    return {"tools": tools}


@router.post("/tools/call", response_model=MCPToolResponse)
def call_research_agent_tool(
    request: MCPToolRequest,
    server: ResearchAgentMCPServer = Depends(get_research_agent_mcp_server),
) -> MCPToolResponse:
    return server.call_tool(request)


@router.post("/{run_id}/execute-local", response_model=ResearchRun)
def execute_research_run_local(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
    intake_service: CollectionIntakeService = Depends(get_collection_intake_service),
    paper_processing_service: PaperProcessingService | None = Depends(
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
