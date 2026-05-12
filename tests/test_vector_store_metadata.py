import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk
from app.services.vector_store import VectorStore


def _make_chunk(paper_id: str, section: str, content: str, seq: int) -> Chunk:
    return Chunk(
        chunk_id=f"{paper_id}_chunk_{seq:04d}",
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        section=section,
        content=content,
    )


def test_vector_store_reports_backend_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        assert store.backend_name() == "json"


def test_vector_store_metadata_includes_store_path_and_counts():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        store.add_chunks([_make_chunk("paper_A", "Method", "content", 1)], [[1.0, 0.0]])

        meta = store.metadata()

        assert meta["backend"] == "json"
        assert meta["chunk_count"] == 1
        assert meta["paper_count"] == 1
        assert meta["store_path"].endswith("vector_store.json")


def test_vector_store_query_returns_relevant_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        store.add_chunks(
            [
                _make_chunk("paper_A", "Method", "content A", 1),
                _make_chunk("paper_B", "Method", "content B", 2),
            ],
            [[1.0, 0.0], [0.0, 1.0]],
        )

        results = store.query([1.0, 0.0], top_k=1)

        assert len(results) == 1
        assert results[0]["paper_id"] == "paper_A"
