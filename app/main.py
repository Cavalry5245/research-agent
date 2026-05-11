import os
import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas import (
    CompareRequest,
    CompareResponse,
    DeletePaperResponse,
    HealthResponse,
    IndexStatusResponse,
    LibraryIndexStatusResponse,
    NoteGenerateResponse,
    NoteReadResponse,
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
from app.services.llm_client import LLMClient
from app.services.markdown_exporter import save_markdown
from app.services.note_generator import generate_note
from app.services.paper_compare import compare_papers, save_compare_result
from app.services.paper_manager import delete_paper_assets
from app.services.paper_qa import answer_question
from app.services.paper_status import get_index_status, get_library_status
from app.services.pdf_parser import (
    find_pdf_path,
    generate_paper_id,
    list_papers,
    load_parsed_result,
    parse_pdf,
    save_parse_result,
)
from app.services.vector_store import VectorStore

app = FastAPI(title="ResearchAgent", version="0.1.0")


def _resolve_metadata_dir() -> str:
    return settings.metadata_dir


def _resolve_note_dir() -> str:
    return settings.note_dir


def _resolve_upload_dir() -> str:
    return settings.upload_dir


def _paper_not_found(paper_id: str):
    raise HTTPException(status_code=404, detail=f"论文 {paper_id} 不存在")


# ── Health ───────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", project="ResearchAgent")


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


@app.post("/papers/{paper_id}/index", response_model=IndexStatusResponse)
async def index_paper(paper_id: str):
    try:
        data = load_parsed_result(paper_id, _resolve_metadata_dir())
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    parsed = PaperParseResult(**data)
    chunks = chunk_paper(parsed)

    if not chunks:
        raise HTTPException(status_code=400, detail="论文内容为空，无法生成索引块")

    texts = [c.content for c in chunks]
    embeddings = _get_embedding_client().embed_texts(texts)
    _get_vector_store().add_chunks(chunks, embeddings)

    return IndexStatusResponse(
        paper_id=paper_id,
        status="indexed",
        chunks_indexed=len(chunks),
    )


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
        content = compare_papers(
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

    output_path = save_compare_result(content, _resolve_note_dir())

    return CompareResponse(
        paper_ids=req.paper_ids,
        status="compared",
        output_path=output_path,
        content=content,
    )


# ── QA ───────────────────────────────────────────────────────────────────────


_vector_store: VectorStore | None = None
_embedding_client: EmbeddingClient | None = None
_llm_client: LLMClient | None = None


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


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


@app.post("/qa", response_model=QAResponse)
async def qa_endpoint(req: QARequest):
    try:
        result = answer_question(
            question=req.question,
            vector_store=_get_vector_store(),
            embedding_client=_get_embedding_client(),
            llm_client=_get_llm_client(),
            paper_id=req.paper_id,
            top_k=req.top_k,
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
