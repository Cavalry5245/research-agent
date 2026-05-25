from collections import defaultdict

from app.schemas import IndexJobStatusResponse, JobStatusResponse
from app.services.vector_store import VectorStore


def get_index_status(vector_store: VectorStore, paper_id: str) -> dict:
    chunks = vector_store.list_chunks(paper_id=paper_id)
    sections = sorted({chunk["section"] for chunk in chunks})
    return {
        "paper_id": paper_id,
        "indexed": bool(chunks),
        "chunk_count": len(chunks),
        "sections": sections,
    }


def get_library_status(vector_store: VectorStore) -> dict:
    chunks = vector_store.list_chunks()
    grouped: dict[str, dict] = defaultdict(lambda: {"paper_id": "", "chunk_count": 0, "sections": set()})

    for chunk in chunks:
        paper_id = chunk["paper_id"]
        grouped[paper_id]["paper_id"] = paper_id
        grouped[paper_id]["chunk_count"] += 1
        grouped[paper_id]["sections"].add(chunk["section"])

    papers = sorted(
        [
            {
                "paper_id": item["paper_id"],
                "chunk_count": item["chunk_count"],
                "sections": sorted(item["sections"]),
            }
            for item in grouped.values()
        ],
        key=lambda item: (-item["chunk_count"], item["paper_id"]),
    )

    return {
        "total_chunks": len(chunks),
        "paper_count": len(papers),
        "papers": papers,
    }


def build_job_status(
    *,
    job_id: str,
    job_type: str,
    status: str,
    created_at: str,
    updated_at: str,
    paper_id: str | None = None,
    paper_ids: list[str] | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    progress: float = 0.0,
    result: dict | None = None,
    error: str | None = None,
    retry_of: str | None = None,
) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job_id,
        job_type=job_type,
        paper_id=paper_id,
        paper_ids=paper_ids or [],
        status=status,
        progress=progress,
        result=result,
        error=error,
        retry_of=retry_of,
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        updated_at=updated_at,
    )


def build_index_job_status(
    *,
    job_id: str,
    paper_id: str,
    status: str,
    created_at: str,
    updated_at: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    chunks_indexed: int = 0,
    already_indexed: bool = False,
    progress: float = 0.0,
    parse_seconds: float = 0.0,
    chunk_seconds: float = 0.0,
    embedding_seconds: float = 0.0,
    persist_seconds: float = 0.0,
    total_seconds: float = 0.0,
    result: dict | None = None,
    error: str | None = None,
) -> IndexJobStatusResponse:
    return IndexJobStatusResponse(
        job_id=job_id,
        job_type="paper_index",
        paper_id=paper_id,
        status=status,
        progress=progress,
        chunks_indexed=chunks_indexed,
        already_indexed=already_indexed,
        parse_seconds=parse_seconds,
        chunk_seconds=chunk_seconds,
        embedding_seconds=embedding_seconds,
        persist_seconds=persist_seconds,
        total_seconds=total_seconds,
        result=result,
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        updated_at=updated_at,
        error=error,
    )
