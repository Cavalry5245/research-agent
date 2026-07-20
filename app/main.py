import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

# Fix SSL certificate issue for httpx
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse

from app.config import settings
from app.logging_config import configure_logging, get_logger
from app.middleware.error_handler import (
    http_exception_handler,
    unhandled_exception_handler,
)
from app.middleware.byok import ByokMiddleware
from app.middleware.tracing import RequestIDMiddleware
from app.schemas import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    CompareRequest,
    CompareResponse,
    DeletePaperResponse,
    HealthResponse,
    IndexJobStatusResponse,
    IndexStatusResponse,
    JobListResponse,
    JobRetryResponse,
    JobStatusResponse,
    KBAddPaperRequest,
    KBCreateRequest,
    KBListResponse,
    KBResponse,
    LibraryIndexStatusResponse,
    NoteGenerateResponse,
    NoteReadResponse,
    NoteStatusItem,
    NoteStatusListResponse,
    PaperComparisonResult,
    PaperIndexDetailResponse,
    PaperListItem,
    PaperListResponse,
    PaperParseResult,
    PaperTitleUpdateRequest,
    PaperTitleUpdateResponse,
    PaperUploadResponse,
    ParseStatusResponse,
    QARequest,
    QAResponse,
    SourceItem,
    SystemStatusResponse,
    ZoteroImportCollection,
    ZoteroImportCollectionsResponse,
    ZoteroImportItem,
    ZoteroImportItemsResponse,
    ZoteroImportRequest,
    ZoteroImportResponse,
    ZoteroImportResultItem,
)
from app.research_workflow.mcp_health import build_mcp_hub_health
from app.research_workflow.store import FileResearchRunStore
from app.research_workflow.zotero_intake import (
    ZoteroLocalHttpClient,
    resolve_first_existing_pdf,
)
from app.services.chunker import chunk_paper
from app.services.chroma_rebuild import redact_error
from app.services.embedding_client import EmbeddingClient
from app.services.job_store import FileJobStore, InMemoryJobStore, utc_now_iso
from app.services.llm_client import LLMClient
from app.services.markdown_exporter import save_markdown
from app.services.note_generator import generate_note
from app.services.paper_compare import compare_papers, save_compare_result
from app.services.paper_manager import delete_paper_assets
from app.services.paper_qa import answer_question
from app.services.qa_memory import QAMemoryService
from app.services.paper_status import (
    build_index_job_status,
    build_job_status,
    get_index_status,
    get_library_status,
)
from app.services.pdf_parser import (
    find_pdf_path,
    generate_paper_id,
    list_papers,
    load_parsed_result,
    parse_pdf,
    save_parse_result,
    update_parsed_title,
)
from app.services.vector_store import VectorStore

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="ResearchAgent", version="0.1.0")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(ByokMiddleware)

from app.routers.conversations import get_memory_store, router as conversations_router

app.include_router(conversations_router)

from app.routers.traces import router as traces_router

app.include_router(traces_router)

from app.routers.research_runs import router as research_runs_router

app.include_router(research_runs_router)

from app.research_pipeline.router import router as research_pipeline_router

app.include_router(research_pipeline_router)


class JobStore(Protocol):
    def upsert(self, job: JobStatusResponse) -> JobStatusResponse: ...

    def get(self, job_id: str) -> JobStatusResponse | None: ...

    def list(self) -> list[JobStatusResponse]: ...

    def clear(self) -> None: ...


def _resolve_metadata_dir() -> str:
    return settings.metadata_dir


def _resolve_note_dir() -> str:
    return settings.note_dir


def _resolve_upload_dir() -> str:
    return settings.upload_dir


def _storage_is_writable() -> bool:
    for directory in [_resolve_upload_dir(), _resolve_note_dir(), _resolve_metadata_dir()]:
        probe = os.path.join(
            directory,
            f".system_status_probe.{os.getpid()}.{time.time_ns()}",
        )
        try:
            os.makedirs(directory, exist_ok=True)
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
        except OSError:
            return False
        finally:
            try:
                if os.path.exists(probe):
                    os.remove(probe)
            except OSError:
                return False
    return True


def _get_research_run_service_for_status() -> FileResearchRunStore:
    storage_root = Path(settings.metadata_dir).parent
    return FileResearchRunStore(storage_root / "research_runs.json")


def _paper_not_found(paper_id: str):
    raise HTTPException(status_code=404, detail=f"论文 {paper_id} 不存在")


# ── Health ───────────────────────────────────────────────────────────────────


_SAFE_VECTOR_STRING_FIELDS = (
    "backend",
    "store_path",
    "collection_name",
    "build_status",
    "embedding_model",
    "persist_dir",
)
_STATUS_URL_RE = re.compile(r"(?i)https?://[^\s,;]+")


def _safe_vector_error(exc: Exception) -> str:
    # Preserve the endpoint's historical plain-message shape while applying the
    # rebuild pipeline's adversarially tested credential redaction.
    redacted = redact_error(str(exc))
    return _STATUS_URL_RE.sub("[REDACTED_URL]", redacted)


def _vector_store_status_payload() -> dict:
    payload = {
        "available": False,
        "backend": None,
        "store_path": None,
        "collection_name": None,
        "build_status": None,
        "embedding_dimension": None,
        "embedding_model": None,
        "schema_version": None,
        "chunk_count": 0,
        "paper_count": None,
        "persist_dir": None,
        "error": None,
    }
    try:
        vector_store = _get_vector_store()
        vector_meta = vector_store.metadata()
        if not isinstance(vector_meta, dict):
            raise RuntimeError("vector store metadata must be a mapping")

        backend_name = vector_store.backend_name()
        chunk_count = vector_store.count()
        if type(chunk_count) is not int or chunk_count < 0:
            raise RuntimeError("vector store count must be a non-negative integer")

        for field in _SAFE_VECTOR_STRING_FIELDS:
            value = vector_meta.get(field)
            if type(value) is str:
                payload[field] = value
        for field in ("embedding_dimension", "schema_version"):
            value = vector_meta.get(field)
            if type(value) is int and value > 0:
                payload[field] = value
        paper_count = vector_meta.get("paper_count")
        if type(paper_count) is int and paper_count >= 0:
            payload["paper_count"] = paper_count
        payload["chunk_count"] = chunk_count

        metadata_backend = vector_meta.get("backend")
        available = (
            type(backend_name) is str
            and backend_name in {"json", "chroma"}
            and metadata_backend == backend_name
        )
        if backend_name == "json":
            for field in ("load_failed", "degraded"):
                value = vector_meta.get(field, False)
                available = available and type(value) is bool and not value
        elif backend_name == "chroma":
            dimension = vector_meta.get("embedding_dimension")
            schema_version = vector_meta.get("schema_version")
            available = available and all(
                (
                    vector_meta.get("collection_name")
                    == settings.chroma_collection_name,
                    vector_meta.get("build_status") == "ready",
                    type(dimension) is int and dimension > 0,
                    vector_meta.get("embedding_model") == settings.embedding_model,
                    type(schema_version) is int and schema_version == 1,
                )
            )
        payload["available"] = available
        if not available:
            payload["error"] = "vector store is not ready"
    except Exception as exc:
        payload["error"] = _safe_vector_error(exc)
    return payload


@app.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check():
    storage_dirs = [_resolve_upload_dir(), _resolve_note_dir(), _resolve_metadata_dir()]
    storage_writable = True
    for directory in storage_dirs:
        try:
            os.makedirs(directory, exist_ok=True)
            probe = os.path.join(directory, ".healthcheck")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
        except OSError:
            storage_writable = False
            break

    vector_store_available = _vector_store_status_payload()["available"]

    status = "ok" if storage_writable and vector_store_available else "degraded"
    return HealthResponse(
        status=status,
        project="ResearchAgent",
        storage_writable=storage_writable,
        vector_store_available=vector_store_available,
        config={
            "llm_configured": bool(settings.llm_api_key),
            "embedding_model_configured": bool(settings.embedding_model),
            "vector_store_configured": bool(settings.vector_store),
        },
    )


@app.get("/system/status", response_model=SystemStatusResponse, summary="System status")
async def system_status():
    storage_root = Path(settings.metadata_dir).parent
    storage_writable = _storage_is_writable()

    vector_payload = _vector_store_status_payload()

    try:
        paper_count = len(list_papers(_resolve_metadata_dir()))
    except Exception:
        paper_count = 0

    try:
        task_count = len(_get_job_store().list())
    except Exception:
        task_count = 0

    try:
        research_store = _get_research_run_service_for_status()
        if hasattr(research_store, "list_runs"):
            research_runs = research_store.list_runs()
        else:
            research_runs = research_store.list()
        mcp_hub = build_mcp_hub_health(
            service=None,
            storage_root=storage_root,
        )
    except Exception as exc:
        research_runs = []
        mcp_hub = [
            {
                "tool_name": "MCP Hub",
                "provider": "system",
                "available": False,
                "fallback_available": False,
                "fallback_active": False,
                "message": str(exc),
                "tool_count": 0,
                "state": "unavailable",
            }
        ]

    status = "ok" if storage_writable and vector_payload["available"] else "degraded"

    return SystemStatusResponse(
        project="ResearchAgent",
        status=status,
        counts={
            "papers": paper_count,
            "chunks": int(vector_payload["chunk_count"]),
            "tasks": task_count,
            "research_runs": len(research_runs),
        },
        models={
            "llm": {
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "configured": bool(settings.llm_api_key),
            },
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "configured": bool(settings.embedding_model),
                "device": settings.embedding_device,
                "batch_size": settings.embedding_batch_size,
            },
        },
        vector_store=vector_payload,
        storage={
            "upload_dir": settings.upload_dir,
            "note_dir": settings.note_dir,
            "metadata_dir": settings.metadata_dir,
            "writable": storage_writable,
        },
        integrations={
            "zotero": {
                "enabled": (
                    settings.enable_zotero
                    or settings.zotero_local
                    or settings.zotero_mcp_enabled
                ),
                "configured": settings.zotero_local
                or bool(settings.zotero_mcp_command),
                "local_api_url": (
                    f"http://127.0.0.1:23119/api/users/{settings.zotero_library_id}"
                ),
            },
            "obsidian": {
                "enabled": bool(settings.obsidian_vault_root),
                "configured": bool(settings.obsidian_vault_root),
                "path": settings.obsidian_vault_root,
            },
        },
        mcp_hub=mcp_hub,
    )


# ── List papers ──────────────────────────────────────────────────────────────


@app.get("/papers", response_model=PaperListResponse)
async def list_papers_endpoint():
    papers = list_papers(_resolve_metadata_dir())
    items = [PaperListItem(**p) for p in papers]
    return PaperListResponse(count=len(items), papers=items)


# ── Upload ───────────────────────────────────────────────────────────────────


def _apply_paper_source_metadata(
    result: PaperParseResult,
    *,
    source: str,
    source_id: str | None = None,
    source_metadata: dict | None = None,
    created_at: str | None = None,
) -> PaperParseResult:
    result.created_at = created_at or result.created_at or utc_now_iso()
    result.source = source  # type: ignore[assignment]
    result.source_id = source_id
    result.source_metadata = source_metadata or {}
    return result


def _normalize_duplicate_key(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def _existing_paper_identity_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for paper in list_papers(_resolve_metadata_dir()):
        paper_id = paper.get("paper_id", "")
        if not paper_id:
            continue

        source_id = _normalize_duplicate_key(paper.get("source_id"))
        if source_id:
            index[f"source_id:{source_id}"] = paper_id

        title = _normalize_duplicate_key(paper.get("title"))
        if title:
            index[f"title:{title}"] = paper_id

        try:
            parsed = load_parsed_result(paper_id, _resolve_metadata_dir())
        except FileNotFoundError:
            continue

        doi = _normalize_duplicate_key(parsed.get("source_metadata", {}).get("doi"))
        if doi:
            index[f"doi:{doi}"] = paper_id
    return index


@app.post("/papers/upload", response_model=PaperUploadResponse)
async def upload_paper(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="只支持 PDF 文件上传，请上传 .pdf 格式的文件"
        )

    upload_dir = _resolve_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)

    paper_id = generate_paper_id(upload_dir)

    storage_path = os.path.join(upload_dir, file.filename)
    if os.path.exists(storage_path):
        name, ext = os.path.splitext(file.filename)
        storage_path = os.path.join(upload_dir, f"{name}__new{ext}")

    with open(storage_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = parse_pdf(storage_path, paper_id)
        _apply_paper_source_metadata(result, source="upload")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 解析失败: {e}") from e

    json_path = save_parse_result(result, _resolve_metadata_dir())

    return PaperUploadResponse(
        paper_id=paper_id,
        filename=file.filename,
        status="parsed",
        storage_path=storage_path,
    )


# ── Parse ────────────────────────────────────────────────────────────────────


@app.post("/papers/{paper_id}/parse", response_model=ParseStatusResponse)
async def parse_paper(paper_id: str):
    upload_dir = _resolve_upload_dir()

    try:
        pdf_path = find_pdf_path(paper_id, upload_dir, _resolve_metadata_dir())
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"论文 {paper_id} 的 PDF 文件或解析记录不存在，请先上传 PDF",
        )

    try:
        previous = load_parsed_result(paper_id, _resolve_metadata_dir())
    except FileNotFoundError:
        previous = {}

    try:
        result = parse_pdf(pdf_path, paper_id)
        _apply_paper_source_metadata(
            result,
            source=previous.get("source") or "upload",
            source_id=previous.get("source_id"),
            source_metadata=previous.get("source_metadata") or {},
            created_at=previous.get("created_at"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 解析失败: {e}") from e

    json_path = save_parse_result(result, _resolve_metadata_dir())

    return ParseStatusResponse(
        paper_id=paper_id,
        status="parsed",
        json_path=json_path,
    )


# ── Generate note ────────────────────────────────────────────────────────────


@app.patch("/papers/{paper_id}/title", response_model=PaperTitleUpdateResponse)
async def update_paper_title(paper_id: str, payload: PaperTitleUpdateRequest):
    title = payload.title.strip()
    if len(title) < 3:
        raise HTTPException(status_code=400, detail="Title must be at least 3 characters long")

    data = update_parsed_title(paper_id, _resolve_metadata_dir(), title)
    return PaperTitleUpdateResponse(
        paper_id=paper_id,
        title=data["title"],
        status="updated",
    )


@app.get("/papers/zotero/collections", response_model=ZoteroImportCollectionsResponse)
async def list_paper_zotero_collections(limit: int = 100):
    try:
        collections = ZoteroLocalHttpClient().list_collections(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zotero API unavailable: {e}") from e

    items = [
        ZoteroImportCollection(
            key=collection.key,
            name=collection.name,
            parent_key=collection.parent_key,
            num_items=collection.num_items,
        )
        for collection in collections
    ]
    return ZoteroImportCollectionsResponse(collections=items, count=len(items))


def _zotero_import_item_response(item, existing_index: dict[str, str]) -> ZoteroImportItem:
    pdf_path = resolve_first_existing_pdf([attachment.path for attachment in item.attachments])
    existing_paper_id = (
        existing_index.get(f"source_id:{_normalize_duplicate_key(item.key)}")
        or existing_index.get(f"doi:{_normalize_duplicate_key(item.doi)}")
        or existing_index.get(f"title:{_normalize_duplicate_key(item.title)}")
    )
    return ZoteroImportItem(
        key=item.key,
        title=item.title,
        creators=item.creators,
        year=item.year,
        doi=item.doi,
        has_pdf=pdf_path is not None,
        pdf_path=pdf_path,
        already_imported=existing_paper_id is not None,
        existing_paper_id=existing_paper_id,
    )


@app.get(
    "/papers/zotero/collections/{collection_key}/items",
    response_model=ZoteroImportItemsResponse,
)
async def list_paper_zotero_collection_items(collection_key: str):
    try:
        zotero_items = ZoteroLocalHttpClient().list_collection_items(collection_key)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zotero API unavailable: {e}") from e

    existing_index = _existing_paper_identity_index()
    items = [_zotero_import_item_response(item, existing_index) for item in zotero_items]
    return ZoteroImportItemsResponse(
        collection_key=collection_key,
        items=items,
        count=len(items),
    )


def _unique_upload_path(upload_dir: str, filename: str) -> str:
    stem = Path(filename).stem or "zotero_paper"
    suffix = Path(filename).suffix or ".pdf"
    candidate = Path(upload_dir) / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = Path(upload_dir) / f"{stem}__zotero_{counter}{suffix}"
        counter += 1
    return str(candidate)


@app.post("/papers/zotero/import", response_model=ZoteroImportResponse)
async def import_papers_from_zotero(payload: ZoteroImportRequest):
    try:
        zotero_items = ZoteroLocalHttpClient().list_collection_items(payload.collection_key)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zotero API unavailable: {e}") from e

    items_by_key = {item.key: item for item in zotero_items}
    existing_index = _existing_paper_identity_index()
    upload_dir = _resolve_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)

    imported: list[ZoteroImportResultItem] = []
    skipped: list[ZoteroImportResultItem] = []
    failed: list[ZoteroImportResultItem] = []

    for item_key in payload.item_keys:
        item = items_by_key.get(item_key)
        if item is None:
            failed.append(
                ZoteroImportResultItem(
                    item_key=item_key,
                    title="Unknown Zotero item",
                    status="failed",
                    reason="Item not found in selected collection",
                )
            )
            continue

        duplicate_paper_id = (
            existing_index.get(f"source_id:{_normalize_duplicate_key(item.key)}")
            or existing_index.get(f"doi:{_normalize_duplicate_key(item.doi)}")
            or existing_index.get(f"title:{_normalize_duplicate_key(item.title)}")
        )
        if duplicate_paper_id:
            skipped.append(
                ZoteroImportResultItem(
                    item_key=item.key,
                    title=item.title,
                    paper_id=duplicate_paper_id,
                    status="skipped",
                    reason="Paper already exists",
                )
            )
            continue

        source_pdf_path = resolve_first_existing_pdf(
            [attachment.path for attachment in item.attachments]
        )
        if source_pdf_path is None:
            skipped.append(
                ZoteroImportResultItem(
                    item_key=item.key,
                    title=item.title,
                    status="skipped",
                    reason="No local PDF attachment found",
                )
            )
            continue

        try:
            paper_id = generate_paper_id(upload_dir)
            storage_path = _unique_upload_path(upload_dir, Path(source_pdf_path).name)
            shutil.copyfile(source_pdf_path, storage_path)
            result = parse_pdf(storage_path, paper_id)
            _apply_paper_source_metadata(
                result,
                source="zotero",
                source_id=item.key,
                source_metadata={
                    "collection_key": payload.collection_key,
                    "zotero_item_key": item.key,
                    "doi": item.doi,
                    "creators": item.creators,
                    "year": item.year,
                    "url": item.url,
                },
            )
            save_parse_result(result, _resolve_metadata_dir())
            existing_index[f"source_id:{_normalize_duplicate_key(item.key)}"] = paper_id
            if item.doi:
                existing_index[f"doi:{_normalize_duplicate_key(item.doi)}"] = paper_id
            existing_index[f"title:{_normalize_duplicate_key(result.title)}"] = paper_id
            imported.append(
                ZoteroImportResultItem(
                    item_key=item.key,
                    title=result.title or item.title,
                    paper_id=paper_id,
                    status="imported",
                )
            )
        except Exception as e:
            failed.append(
                ZoteroImportResultItem(
                    item_key=item.key,
                    title=item.title,
                    status="failed",
                    reason=str(e),
                )
            )

    return ZoteroImportResponse(imported=imported, skipped=skipped, failed=failed)


@app.post("/papers/{paper_id}/note", response_model=NoteGenerateResponse)
async def generate_note_endpoint(paper_id: str):
    try:
        content = generate_note(paper_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    note_path = save_markdown(paper_id, content, _resolve_note_dir())

    return NoteGenerateResponse(
        paper_id=paper_id,
        status="generated",
        note_path=note_path,
        content=content,
    )


def _build_note_status_response() -> NoteStatusListResponse:
    note_dir = _resolve_note_dir()
    existing_notes: dict[str, str] = {}
    if os.path.isdir(note_dir):
        for filename in os.listdir(note_dir):
            if filename.endswith("_note.md"):
                existing_notes[filename.removesuffix("_note.md")] = os.path.join(note_dir, filename)

    notes: list[NoteStatusItem] = []
    for paper in list_papers(_resolve_metadata_dir()):
        paper_id = paper.get("paper_id")
        if not paper_id:
            continue

        note_path = existing_notes.get(paper_id) or os.path.join(note_dir, f"{paper_id}_note.md")
        exists = os.path.isfile(note_path)
        generated_at = None
        if exists:
            generated_at = datetime.fromtimestamp(
                os.path.getmtime(note_path),
                timezone.utc,
            ).isoformat()

        notes.append(
            NoteStatusItem(
                paper_id=paper_id,
                exists=exists,
                note_path=note_path if exists else None,
                generated_at=generated_at,
            )
        )

    return NoteStatusListResponse(count=len(notes), notes=notes)


@app.get("/notes/status", response_model=NoteStatusListResponse)
async def list_note_status():
    return _build_note_status_response()


@app.get("/papers/notes/status", response_model=NoteStatusListResponse)
async def list_paper_note_status():
    return _build_note_status_response()


# ── Read note ────────────────────────────────────────────────────────────────


@app.get("/papers/{paper_id}/note", response_model=NoteReadResponse)
async def read_note(paper_id: str):
    note_path = os.path.join(_resolve_note_dir(), f"{paper_id}_note.md")
    if not os.path.isfile(note_path):
        raise HTTPException(
            status_code=404,
            detail=f"论文 {paper_id} 的笔记文件不存在，请先生成笔记 (POST /papers/{paper_id}/note)",
        )
    with open(note_path, "r", encoding="utf-8") as f:
        content = f.read()
    return NoteReadResponse(paper_id=paper_id, note_path=note_path, content=content)


# ── Download ─────────────────────────────────────────────────────────────────


@app.get("/papers/{paper_id}/download")
async def download_note(paper_id: str):
    note_path = os.path.join(_resolve_note_dir(), f"{paper_id}_note.md")
    if not os.path.isfile(note_path):
        raise HTTPException(
            status_code=404,
            detail=f"论文 {paper_id} 的笔记文件不存在，请先生成笔记 (POST /papers/{paper_id}/note)",
        )
    return FileResponse(
        path=note_path,
        media_type="text/markdown",
        filename=f"{paper_id}_note.md",
    )


# ── Index to vector store ────────────────────────────────────────────────────


def _run_index_job(job_id: str, paper_id: str, force: bool, created_at: str) -> None:
    vector_store = _get_vector_store()

    if vector_store.has_paper(paper_id) and not force:
        status = get_index_status(vector_store, paper_id)
        job = build_index_job_status(
            job_id=job_id,
            paper_id=paper_id,
            status="completed",
            created_at=created_at,
            updated_at=created_at,
            progress=1.0,
            chunks_indexed=status["chunk_count"],
            already_indexed=True,
            total_seconds=0.0,
        )
        _get_job_store().upsert(job)
        return

    total_started = time.perf_counter()

    try:
        data = load_parsed_result(paper_id, _resolve_metadata_dir())
    except FileNotFoundError as e:
        failed_at = utc_now_iso()
        failed_job = build_index_job_status(
            job_id=job_id,
            paper_id=paper_id,
            status="failed",
            created_at=created_at,
            started_at=created_at,
            updated_at=failed_at,
            error=str(e),
        )
        _get_job_store().upsert(failed_job)
        return

    parse_seconds = time.perf_counter() - total_started
    parsed = PaperParseResult(**data)

    chunk_started = time.perf_counter()
    chunks = chunk_paper(parsed)
    chunk_seconds = time.perf_counter() - chunk_started

    if not chunks:
        failed_at = utc_now_iso()
        failed_job = build_index_job_status(
            job_id=job_id,
            paper_id=paper_id,
            status="failed",
            created_at=created_at,
            started_at=created_at,
            updated_at=failed_at,
            parse_seconds=parse_seconds,
            chunk_seconds=chunk_seconds,
            error="论文内容为空，无法生成索引块",
        )
        _get_job_store().upsert(failed_job)
        return

    texts = [c.content for c in chunks]
    running_at = utc_now_iso()
    _get_job_store().upsert(
        build_index_job_status(
            job_id=job_id,
            paper_id=paper_id,
            status="running",
            created_at=created_at,
            started_at=running_at,
            updated_at=running_at,
            progress=0.25,
            chunks_indexed=0,
            already_indexed=False,
            parse_seconds=parse_seconds,
            chunk_seconds=chunk_seconds,
        )
    )

    try:
        embedding_started = time.perf_counter()
        embedding_client = _get_embedding_client()
        embeddings = embedding_client.embed_texts(texts)
        embedding_seconds = time.perf_counter() - embedding_started

        persist_started = time.perf_counter()
        vector_store.add_chunks(chunks, embeddings)
        persist_seconds = time.perf_counter() - persist_started
        total_seconds = time.perf_counter() - total_started
        completed_at = utc_now_iso()

        job = build_index_job_status(
            job_id=job_id,
            paper_id=paper_id,
            status="completed",
            created_at=created_at,
            started_at=running_at,
            completed_at=completed_at,
            updated_at=completed_at,
            progress=1.0,
            chunks_indexed=len(chunks),
            already_indexed=False,
            parse_seconds=parse_seconds,
            chunk_seconds=chunk_seconds,
            embedding_seconds=embedding_seconds,
            persist_seconds=persist_seconds,
            total_seconds=total_seconds,
        )
        _get_job_store().upsert(job)
        logger.info(
            "index_job_completed",
            extra={
                "ra_job_id": job_id,
                "ra_paper_id": paper_id,
                "ra_duration_ms": round(total_seconds * 1000, 2),
            },
        )
    except Exception as exc:
        failed_at = utc_now_iso()
        total_seconds = time.perf_counter() - total_started
        logger.error(
            "index_job_failed",
            exc_info=exc,
            extra={"ra_job_id": job_id, "ra_paper_id": paper_id},
        )
        _get_job_store().upsert(
            build_index_job_status(
                job_id=job_id,
                paper_id=paper_id,
                status="failed",
                created_at=created_at,
                started_at=running_at,
                updated_at=failed_at,
                progress=0.25,
                chunks_indexed=0,
                already_indexed=False,
                parse_seconds=parse_seconds,
                chunk_seconds=chunk_seconds,
                total_seconds=total_seconds,
                error=str(exc),
            )
        )


@app.post(
    "/papers/{paper_id}/index", response_model=IndexStatusResponse, status_code=202
)
async def index_paper(
    paper_id: str,
    background_tasks: BackgroundTasks,
    response: Response,
    force: bool = False,
):
    vector_store = _get_vector_store()
    created_at = utc_now_iso()
    job_id = f"job_{paper_id}_{int(time.time() * 1000)}"

    if vector_store.has_paper(paper_id) and not force:
        status = get_index_status(vector_store, paper_id)
        job = build_index_job_status(
            job_id=job_id,
            paper_id=paper_id,
            status="completed",
            created_at=created_at,
            started_at=created_at,
            completed_at=created_at,
            updated_at=created_at,
            progress=1.0,
            chunks_indexed=status["chunk_count"],
            already_indexed=True,
            total_seconds=0.0,
        )
        _get_job_store().upsert(job)
        response.status_code = 200
        return job

    queued_job = build_index_job_status(
        job_id=job_id,
        paper_id=paper_id,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
        progress=0.0,
        chunks_indexed=0,
        already_indexed=False,
    )
    _get_job_store().upsert(queued_job)
    background_tasks.add_task(_run_index_job, job_id, paper_id, force, created_at)
    return queued_job


# ── Tasks and jobs ────────────────────────────────────────────────────────────


def _new_job_id(job_type: str, subject: str) -> str:
    safe_subject = subject.replace("/", "_")
    return f"job_{job_type}_{safe_subject}_{int(time.time() * 1000)}"


def _is_cancelled(job_id: str) -> bool:
    job = _get_job_store().get(job_id)
    return job is not None and job.status == "cancelled"


def _run_note_job(job_id: str, paper_id: str, created_at: str) -> None:
    if _is_cancelled(job_id):
        return
    started_at = utc_now_iso()
    _get_job_store().upsert(
        build_job_status(
            job_id=job_id,
            job_type="note_generation",
            paper_id=paper_id,
            status="running",
            created_at=created_at,
            started_at=started_at,
            updated_at=started_at,
            progress=0.2,
        )
    )
    try:
        content = generate_note(paper_id)
        if _is_cancelled(job_id):
            return
        note_path = save_markdown(paper_id, content, _resolve_note_dir())
        completed_at = utc_now_iso()
        _get_job_store().upsert(
            build_job_status(
                job_id=job_id,
                job_type="note_generation",
                paper_id=paper_id,
                status="completed",
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
                updated_at=completed_at,
                progress=1.0,
                result={
                    "paper_id": paper_id,
                    "note_path": note_path,
                    "content_preview": content[:500],
                    "content_length": len(content),
                },
            )
        )
    except Exception as exc:
        failed_at = utc_now_iso()
        logger.error(
            "note_job_failed",
            exc_info=exc,
            extra={"ra_job_id": job_id, "ra_paper_id": paper_id},
        )
        _get_job_store().upsert(
            build_job_status(
                job_id=job_id,
                job_type="note_generation",
                paper_id=paper_id,
                status="failed",
                created_at=created_at,
                started_at=started_at,
                updated_at=failed_at,
                progress=0.2,
                error=str(exc),
            )
        )


def _run_compare_job(job_id: str, paper_ids: list[str], created_at: str) -> None:
    if _is_cancelled(job_id):
        return
    started_at = utc_now_iso()
    _get_job_store().upsert(
        build_job_status(
            job_id=job_id,
            job_type="paper_comparison",
            paper_ids=paper_ids,
            status="running",
            created_at=created_at,
            started_at=started_at,
            updated_at=started_at,
            progress=0.2,
        )
    )
    try:
        comparison = compare_papers(
            paper_ids,
            _resolve_metadata_dir(),
            llm_client=_get_llm_client(),
        )
        if _is_cancelled(job_id):
            return
        output_path = save_compare_result(comparison.markdown, _resolve_note_dir())
        completed_at = utc_now_iso()
        _get_job_store().upsert(
            build_job_status(
                job_id=job_id,
                job_type="paper_comparison",
                paper_ids=paper_ids,
                status="completed",
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
                updated_at=completed_at,
                progress=1.0,
                result={
                    "paper_ids": paper_ids,
                    "output_path": output_path,
                    "content_preview": comparison.markdown[:500],
                    "content_length": len(comparison.markdown),
                },
            )
        )
    except Exception as exc:
        failed_at = utc_now_iso()
        logger.error(
            "compare_job_failed",
            exc_info=exc,
            extra={"ra_job_id": job_id, "ra_paper_ids": paper_ids},
        )
        _get_job_store().upsert(
            build_job_status(
                job_id=job_id,
                job_type="paper_comparison",
                paper_ids=paper_ids,
                status="failed",
                created_at=created_at,
                started_at=started_at,
                updated_at=failed_at,
                progress=0.2,
                error=str(exc),
            )
        )


def _dump_legacy_job(job: JobStatusResponse) -> dict:
    payload = job.model_dump(mode="json")
    if job.job_type == "paper_index":
        payload.pop("paper_ids", None)
        payload.pop("result", None)
        payload.pop("retry_of", None)
    return payload


@app.get("/jobs")
async def list_jobs_endpoint():
    jobs = _get_job_store().list()
    return {"count": len(jobs), "jobs": [_dump_legacy_job(job) for job in jobs]}


@app.get("/jobs/{job_id}")
async def job_status_endpoint(job_id: str):
    job = _get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    return _dump_legacy_job(job)


@app.get(
    "/tasks",
    response_model=JobListResponse,
    summary="List background tasks",
    description="列出 index、note、compare 等后台任务的当前状态。",
)
async def list_tasks_endpoint():
    jobs = _get_job_store().list()
    return JobListResponse(count=len(jobs), jobs=jobs)


@app.get(
    "/tasks/{job_id}",
    response_model=JobStatusResponse,
    summary="Get background task status",
    description="按 task_id 查询后台任务状态、进度、结果摘要和错误信息。",
)
async def task_status_endpoint(job_id: str):
    job = _get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    return job


@app.get(
    "/tasks/{job_id}/result",
    summary="Get background task result",
    description="获取已完成任务的 result 字段；任务未完成时返回 409。",
)
async def task_result_endpoint(job_id: str):
    job = _get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"任务 {job_id} 尚未完成")
    return job.result or {}


@app.delete(
    "/tasks/{job_id}",
    response_model=JobStatusResponse,
    summary="Cancel background task",
    description="取消 queued/running 后台任务；已完成、失败或已取消任务返回 409。",
)
async def cancel_task_endpoint(job_id: str):
    job = _get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    if job.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail=f"任务 {job_id} 已结束，无法取消")
    now = utc_now_iso()
    cancelled = build_job_status(
        job_id=job.job_id,
        job_type=job.job_type,
        paper_id=job.paper_id,
        paper_ids=job.paper_ids,
        status="cancelled",
        created_at=job.created_at.isoformat(),
        started_at=(job.started_at or job.created_at).isoformat(),
        completed_at=now,
        updated_at=now,
        progress=job.progress,
        result=job.result,
        error="任务已取消",
        retry_of=job.retry_of,
    )
    _get_job_store().upsert(cancelled)
    return cancelled


@app.post(
    "/tasks/{job_id}/retry",
    response_model=JobRetryResponse,
    status_code=202,
    summary="Retry failed background task",
    description="为 failed 的 note/compare 任务创建新的 retry 任务。",
)
async def retry_task_endpoint(job_id: str, background_tasks: BackgroundTasks):
    job = _get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    if job.status != "failed":
        raise HTTPException(
            status_code=409, detail=f"任务 {job_id} 不是失败状态，无法重试"
        )

    created_at = utc_now_iso()
    if job.job_type == "note_generation" and job.paper_id:
        retry_job_id = _new_job_id("note_generation", job.paper_id)
        retry_job = build_job_status(
            job_id=retry_job_id,
            job_type="note_generation",
            paper_id=job.paper_id,
            status="queued",
            created_at=created_at,
            updated_at=created_at,
            retry_of=job.job_id,
        )
        _get_job_store().upsert(retry_job)
        background_tasks.add_task(_run_note_job, retry_job_id, job.paper_id, created_at)
        return JobRetryResponse(original_job_id=job.job_id, retry_job=retry_job)

    if job.job_type == "paper_comparison" and job.paper_ids:
        retry_job_id = _new_job_id("paper_comparison", "_".join(job.paper_ids))
        retry_job = build_job_status(
            job_id=retry_job_id,
            job_type="paper_comparison",
            paper_ids=job.paper_ids,
            status="queued",
            created_at=created_at,
            updated_at=created_at,
            retry_of=job.job_id,
        )
        _get_job_store().upsert(retry_job)
        background_tasks.add_task(
            _run_compare_job, retry_job_id, job.paper_ids, created_at
        )
        return JobRetryResponse(original_job_id=job.job_id, retry_job=retry_job)

    raise HTTPException(status_code=400, detail=f"任务 {job.job_type} 暂不支持重试")


@app.post(
    "/tasks/note/{paper_id}",
    response_model=JobStatusResponse,
    status_code=202,
    summary="Submit note generation task",
    description="提交论文笔记生成后台任务，返回可查询的 task_id。",
)
async def submit_note_task(paper_id: str, background_tasks: BackgroundTasks):
    created_at = utc_now_iso()
    job_id = _new_job_id("note_generation", paper_id)
    queued_job = build_job_status(
        job_id=job_id,
        job_type="note_generation",
        paper_id=paper_id,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
    )
    _get_job_store().upsert(queued_job)
    background_tasks.add_task(_run_note_job, job_id, paper_id, created_at)
    return queued_job


@app.post(
    "/tasks/compare",
    response_model=JobStatusResponse,
    status_code=202,
    summary="Submit paper comparison task",
    description="提交多论文对比后台任务，返回可查询的 task_id。",
)
async def submit_compare_task(req: CompareRequest, background_tasks: BackgroundTasks):
    if len(req.paper_ids) < 2:
        raise HTTPException(status_code=400, detail="请选择至少 2 篇论文进行对比")
    if len(req.paper_ids) > 5:
        raise HTTPException(status_code=400, detail="最多支持 5 篇论文对比")
    created_at = utc_now_iso()
    job_id = _new_job_id("paper_comparison", "_".join(req.paper_ids))
    queued_job = build_job_status(
        job_id=job_id,
        job_type="paper_comparison",
        paper_ids=req.paper_ids,
        status="queued",
        created_at=created_at,
        updated_at=created_at,
    )
    _get_job_store().upsert(queued_job)
    background_tasks.add_task(_run_compare_job, job_id, req.paper_ids, created_at)
    return queued_job


# ── Delete paper ─────────────────────────────────────────────────────────────


@app.get("/papers/{paper_id}/index-status", response_model=PaperIndexDetailResponse)
async def paper_index_status_endpoint(paper_id: str):
    status = get_index_status(_get_vector_store(), paper_id)
    return PaperIndexDetailResponse(**status)


@app.get("/library/index-status", response_model=LibraryIndexStatusResponse)
async def library_index_status_endpoint():
    status = get_library_status(_get_vector_store())
    return LibraryIndexStatusResponse(**status)


@app.delete("/papers/{paper_id}", response_model=DeletePaperResponse)
async def delete_paper_endpoint(paper_id: str):
    try:
        result = delete_paper_assets(
            paper_id=paper_id,
            upload_dir=_resolve_upload_dir(),
            metadata_dir=_resolve_metadata_dir(),
            note_dir=_resolve_note_dir(),
            vector_store=_get_vector_store(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return DeletePaperResponse(**result)


# ── Compare papers ────────────────────────────────────────────────────────────


@app.post("/papers/compare", response_model=CompareResponse)
async def compare_papers_endpoint(req: CompareRequest):
    if len(req.paper_ids) < 2:
        raise HTTPException(status_code=400, detail="请选择至少 2 篇论文进行对比")
    if len(req.paper_ids) > 5:
        raise HTTPException(status_code=400, detail="最多支持 5 篇论文对比")

    try:
        comparison = compare_papers(
            req.paper_ids,
            _resolve_metadata_dir(),
            llm_client=_get_llm_client(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    output_path = save_compare_result(comparison.markdown, _resolve_note_dir())

    return CompareResponse(
        paper_ids=req.paper_ids,
        status="compared",
        output_path=output_path,
        content=comparison.markdown,
        comparison=comparison,
    )


# ── QA ───────────────────────────────────────────────────────────────────────


_vector_store: VectorStore | None = None
_embedding_client: EmbeddingClient | None = None
_llm_client: LLMClient | None = None
_job_store: JobStore | None = None


def _get_job_store() -> JobStore:
    global _job_store
    if _job_store is None:
        job_store_path = os.getenv("RESEARCH_AGENT_JOB_STORE_PATH")
        if job_store_path:
            _job_store = FileJobStore(job_store_path)
        else:
            _job_store = InMemoryJobStore()
    return _job_store


def _get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def _get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


_reranker = None


def _get_reranker():
    global _reranker
    if not settings.enable_rerank:
        return None
    if _reranker is None:
        from app.services.reranker import CrossEncoderReranker

        _reranker = CrossEncoderReranker(model_name=settings.rerank_model)
    return _reranker


_bm25_retriever = None
_hybrid_retriever = None
_hyde_retriever = None


def _get_retriever():
    global _bm25_retriever, _hybrid_retriever, _hyde_retriever
    mode = settings.retriever
    if mode == "vector":
        return None
    if mode == "bm25":
        if _bm25_retriever is None:
            from app.services.bm25_retriever import BM25Retriever

            _bm25_retriever = BM25Retriever(_get_vector_store())
        return _bm25_retriever
    if mode == "hybrid":
        if _hybrid_retriever is None:
            from app.services.bm25_retriever import BM25Retriever
            from app.services.hybrid_retriever import HybridRetriever

            bm25 = _bm25_retriever or BM25Retriever(_get_vector_store())
            _hybrid_retriever = HybridRetriever(
                vector_store=_get_vector_store(),
                embedding_client=_get_embedding_client(),
                bm25_retriever=bm25,
                alpha=settings.hybrid_alpha,
                recall_top_k=settings.hybrid_recall_top_k,
            )
        return _hybrid_retriever
    if mode == "hyde":
        if _hyde_retriever is None:
            from app.services.hyde import HyDE

            _hyde_retriever = HyDE(
                llm_client=_get_llm_client(),
                embedding_client=_get_embedding_client(),
                vector_store=_get_vector_store(),
            )
        return _hyde_retriever
    return None


@app.post("/qa", response_model=QAResponse)
async def qa_endpoint(req: QARequest):
    try:
        reranker = _get_reranker()
        retriever = _get_retriever()
        service = QAMemoryService(
            store=get_memory_store(),
            llm_client=_get_llm_client(),
        )

        def run_answer_question(
            question: str,
            paper_id: str | None = None,
            top_k: int = 5,
            conversation_summary: str = "",
            recent_turns: str = "",
            original_question: str | None = None,
        ):
            return answer_question(
                question=question,
                vector_store=_get_vector_store(),
                embedding_client=_get_embedding_client(),
                llm_client=_get_llm_client(),
                paper_id=paper_id,
                top_k=settings.rerank_top_k if reranker else top_k,
                reranker=reranker,
                recall_top_k=settings.rerank_recall_top_k if reranker else None,
                retriever=retriever,
                conversation_summary=conversation_summary,
                recent_turns=recent_turns,
                original_question=original_question,
            )

        result = service.ask(
            question=req.question,
            answer_fn=run_answer_question,
            paper_id=req.paper_id,
            top_k=req.top_k,
            conversation_id=req.conversation_id,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return QAResponse(
        question=result["question"],
        rewritten_question=result.get("rewritten_question"),
        answer=result["answer"],
        sources=[SourceItem(**s) for s in result["sources"]],
        conversation_id=result.get("conversation_id"),
    )


# ── Agent ─────────────────────────────────────────────────────────────────────


@app.post("/agent/execute", response_model=AgentExecuteResponse)
async def agent_execute(req: AgentExecuteRequest):
    from app.agents.paper_research_agent import get_agent

    agent = get_agent()

    try:
        if req.mode == "supervisor":
            result = agent.execute_supervisor(
                req.task,
                context=req.context,
                conversation_id=req.conversation_id,
            )
            return AgentExecuteResponse(
                task=result["task"],
                answer=result["answer"],
                conversation_id=result.get("conversation_id"),
                task_type=result.get("task_type"),
            )
        else:
            chat_history = None
            if req.chat_history:
                chat_history = [
                    {"role": m.role, "content": m.content} for m in req.chat_history
                ]
            result = agent.execute(
                req.task,
                chat_history=chat_history,
                conversation_id=req.conversation_id,
            )
            return AgentExecuteResponse(
                task=result["task"],
                answer=result["answer"],
                conversation_id=result.get("conversation_id"),
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {e}") from e


# ── Knowledge Base management (Phase 4) ──────────────────────────────────────

_kb_manager = None


def _get_kb_manager():
    global _kb_manager
    if _kb_manager is None:
        from app.services.knowledge_base_manager import KnowledgeBaseManager

        _kb_manager = KnowledgeBaseManager()
    return _kb_manager


def _enrich_kb_response(kb: dict) -> dict:
    paper_ids = list(kb.get("paper_ids", []))
    indexed_ids = {
        paper.get("paper_id")
        for paper in get_library_status(_get_vector_store()).get("papers", [])
        if paper.get("paper_id")
    }
    note_dir = _resolve_note_dir()
    noted_ids = {
        paper_id
        for paper_id in paper_ids
        if os.path.isfile(os.path.join(note_dir, f"{paper_id}_note.md"))
    }
    return {
        **kb,
        "paper_count": len(paper_ids),
        "indexed_count": sum(1 for paper_id in paper_ids if paper_id in indexed_ids),
        "noted_count": sum(1 for paper_id in paper_ids if paper_id in noted_ids),
    }


@app.get(
    "/kb",
    response_model=KBListResponse,
    summary="List knowledge bases",
    description="列出所有知识库及其论文数量。",
)
async def list_kbs_endpoint():
    items = _get_kb_manager().list_kbs()
    return KBListResponse(
        count=len(items),
        knowledge_bases=[KBResponse(**_enrich_kb_response(kb)) for kb in items],
    )


@app.post(
    "/kb",
    response_model=KBResponse,
    status_code=201,
    summary="Create knowledge base",
    description="新建独立的知识库，可后续向其中添加论文。",
)
async def create_kb_endpoint(req: KBCreateRequest):
    try:
        kb = _get_kb_manager().create_kb(req.kb_id, req.name, req.description)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return KBResponse(**_enrich_kb_response(kb))


@app.post(
    "/kb/{kb_id}/papers",
    response_model=KBResponse,
    summary="Add paper to knowledge base",
    description="将指定 paper_id 关联到指定知识库。",
)
async def add_paper_to_kb_endpoint(kb_id: str, req: KBAddPaperRequest):
    try:
        kb = _get_kb_manager().add_paper_to_kb(kb_id, req.paper_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return KBResponse(**_enrich_kb_response(kb))


@app.delete(
    "/kb/{kb_id}/papers/{paper_id}",
    response_model=KBResponse,
    summary="Remove paper from knowledge base",
    description="将指定 paper_id 从指定知识库中移除。",
)
async def remove_paper_from_kb_endpoint(kb_id: str, paper_id: str):
    try:
        kb = _get_kb_manager().remove_paper_from_kb(kb_id, paper_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return KBResponse(**_enrich_kb_response(kb))
