import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk
from app.services.paper_status import get_index_status, get_library_status
from app.services.vector_store import VectorStore


def _make_chunk(paper_id: str, section: str, content: str, seq: int) -> Chunk:
    return Chunk(
        chunk_id=f"{paper_id}_chunk_{seq:04d}",
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        section=section,
        content=content,
    )


def test_get_index_status_for_specific_paper():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk("paper_A", "Introduction", "infrared detection intro", 1),
            _make_chunk("paper_A", "Method", "vl attention method", 2),
            _make_chunk("paper_B", "Introduction", "model compression intro", 3),
        ]
        store.add_chunks(chunks, [[0.1, 0.2], [0.2, 0.3], [0.3, 0.4]])

        status = get_index_status(store, "paper_A")
        assert status["paper_id"] == "paper_A"
        assert status["indexed"] is True
        assert status["chunk_count"] == 2
        assert status["sections"] == ["Introduction", "Method"]


def test_get_index_status_for_unindexed_paper():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        status = get_index_status(store, "paper_missing")
        assert status == {
            "paper_id": "paper_missing",
            "indexed": False,
            "chunk_count": 0,
            "sections": [],
        }


def test_get_library_status_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk("paper_A", "Introduction", "infrared detection intro", 1),
            _make_chunk("paper_A", "Method", "vl attention method", 2),
            _make_chunk("paper_B", "Introduction", "model compression intro", 3),
        ]
        store.add_chunks(chunks, [[0.1, 0.2], [0.2, 0.3], [0.3, 0.4]])

        status = get_library_status(store)
        assert status["total_chunks"] == 3
        assert status["paper_count"] == 2
        assert status["papers"][0]["paper_id"] == "paper_A"
        assert status["papers"][0]["chunk_count"] == 2
        assert status["papers"][1]["paper_id"] == "paper_B"
        assert status["papers"][1]["chunk_count"] == 1
