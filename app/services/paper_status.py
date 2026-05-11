from collections import defaultdict

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
