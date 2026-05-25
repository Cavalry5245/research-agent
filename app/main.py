import os
import shutil
import time
from typing import Protocol

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.logging_config import configure_logging, get_logger
from app.middleware.error_handler import http_exception_handler, unhandled_exception_handler
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
    PaperComparisonResult,
    PaperIndexDetailResponse,
    PaperListResponse,
    PaperListItem,
    PaperParseResult,
    PaperUploadResponse,
    ParseStatusResponse,
    QARequest,
    QAResponse,
    SourceItem,
)
from app.services.chunker import chunk_paper
from app.services.embedding_client import EmbeddingClient
from app.services.job_store import FileJobStore, InMemoryJobStore, utc_now_iso
from app.services.llm_client import LLMClient
from app.services.markdown_exporter import save_markdown
from app.services.note_generator import generate_note
from app.services.paper_compare import compare_papers, save_compare_result
from app.services.paper_manager import delete_paper_assets
from app.services.paper_qa import answer_question
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
)
from app.services.vector_store import VectorStore

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="ResearchAgent", version="0.1.0")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(RequestIDMiddleware)


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


def _paper_not_found(paper_id: str):
    raise HTTPException(status_code=404, detail=f"论文 {paper_id} 不存在")


# ── Health ───────────────────────────────────────────────────────────────────


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

    try:
        vector_store_available = _get_vector_store().metadata().get("backend") is not None
    except Exception:
        vector_store_available = False

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


# ── List papers ──────────────────────────────────────────────────────────────


@app.get("/papers", response_model=PaperListResponse)
async def list_papers_endpoint():
    papers = list_papers(_resolve_metadata_dir())
    items = [PaperListItem(**p) for p in papers]
    return PaperListResponse(count=len(items), papers=items)


# ── Upload ───────────────────────────────────────────────────────────────────


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
        result = parse_pdf(pdf_path, paper_id)
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
            extra={"ra_job_id": job_id, "ra_paper_id": paper_id, "ra_duration_ms": round(total_seconds * 1000, 2)},
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


@app.post("/papers/{paper_id}/index", response_model=IndexStatusResponse, status_code=202)
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
        raise HTTPException(status_code=409, detail=f"任务 {job_id} 不是失败状态，无法重试")

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
        background_tasks.add_task(_run_compare_job, retry_job_id, job.paper_ids, created_at)
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


def _get_retriever():
    global _bm25_retriever, _hybrid_retriever
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
    return None


@app.post("/qa", response_model=QAResponse)
async def qa_endpoint(req: QARequest):
    try:
        reranker = _get_reranker()
        retriever = _get_retriever()
        result = answer_question(
            question=req.question,
            vector_store=_get_vector_store(),
            embedding_client=_get_embedding_client(),
            llm_client=_get_llm_client(),
            paper_id=req.paper_id,
            top_k=settings.rerank_top_k if reranker else req.top_k,
            reranker=reranker,
            recall_top_k=settings.rerank_recall_top_k if reranker else None,
            retriever=retriever,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return QAResponse(
        question=result["question"],
        answer=result["answer"],
        sources=[SourceItem(**s) for s in result["sources"]],
    )


# ── Agent ─────────────────────────────────────────────────────────────────────


@app.post("/agent/execute", response_model=AgentExecuteResponse)
async def agent_execute(req: AgentExecuteRequest):
    from app.agents.paper_research_agent import get_agent

    agent = get_agent()
    chat_history = None
    if req.chat_history:
        chat_history = [
            {"role": m.role, "content": m.content} for m in req.chat_history
        ]

    try:
        result = agent.execute(req.task, chat_history=chat_history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {e}") from e

    return AgentExecuteResponse(task=result["task"], answer=result["answer"])


# ── Knowledge Base management (Phase 4) ──────────────────────────────────────

_kb_manager = None


def _get_kb_manager():
    global _kb_manager
    if _kb_manager is None:
        from app.services.knowledge_base_manager import KnowledgeBaseManager

        _kb_manager = KnowledgeBaseManager()
    return _kb_manager


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
        knowledge_bases=[KBResponse(**kb) for kb in items],
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
    return KBResponse(**kb)


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
    return KBResponse(**kb)


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
    return KBResponse(**kb)
