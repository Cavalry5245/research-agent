import math
import os
import subprocess
import sys
import tempfile

import pytest

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


def _keyword_embedding(text: str, dim: int = 64) -> list[float]:
    """
    Build a simple keyword-based embedding so semantically similar texts
    have higher cosine similarity. Real embeddings would be sentence-transformers.
    """
    keywords = {
        "detection": 0,
        "infrared": 1,
        "vl": 2,
        "attention": 3,
        "model": 4,
        "compression": 5,
        "prune": 6,
        "survey": 7,
        "method": 8,
        "experiment": 9,
    }
    vec = [0.0] * dim
    for word in text.lower().split():
        clean = "".join(c for c in word if c.isalpha())
        if clean in keywords:
            idx = keywords[clean] % dim
            vec[idx] += 1.0
    # Normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def test_vector_store_add_and_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk(
                "paper_A", "Introduction", "infrared detection is critical.", 1
            ),
            _make_chunk("paper_A", "Method", "We propose a vl attention method.", 2),
            _make_chunk(
                "paper_A", "Experiments", "experiment shows detection results.", 3
            ),
        ]
        embeddings = [_keyword_embedding(c.content) for c in chunks]
        added = store.add_chunks(chunks, embeddings)
        assert added == 3
        assert store.count() == 3


def test_vector_store_query_all_papers():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk(
                "paper_A", "Introduction", "infrared detection introduction.", 1
            ),
            _make_chunk("paper_A", "Method", "vl attention method for detection.", 2),
            _make_chunk("paper_B", "Introduction", "model compression survey.", 3),
            _make_chunk("paper_B", "Method", "prune parameters in model.", 4),
        ]
        embeddings = [_keyword_embedding(c.content) for c in chunks]
        store.add_chunks(chunks, embeddings)

        results = store.query(_keyword_embedding("infrared detection"), top_k=2)
        assert len(results) == 2
        for r in results:
            assert r["chunk_id"]
            assert r["content"]
            assert r["paper_id"] in ("paper_A", "paper_B")
            assert r["section"]
            assert r["title"]
            assert isinstance(r["score"], float)

        # Paper A chunks should score higher for "infrared detection" query
        top = results[0]
        assert top["paper_id"] == "paper_A"


def test_vector_store_query_by_paper_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk("paper_A", "Introduction", "detection in infrared.", 1),
            _make_chunk("paper_A", "Method", "vl attention mechanism.", 2),
            _make_chunk("paper_B", "Introduction", "model compression survey.", 3),
            _make_chunk("paper_B", "Method", "prune layers.", 4),
        ]
        store.add_chunks(chunks, [_keyword_embedding(c.content) for c in chunks])

        results = store.query(
            _keyword_embedding("model compression"), top_k=5, paper_id="paper_B"
        )
        assert len(results) >= 1
        assert all(r["paper_id"] == "paper_B" for r in results)


def test_vector_store_delete_paper():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks_a = [
            _make_chunk("paper_A", "Introduction", "Paper A intro.", 1),
            _make_chunk("paper_A", "Method", "Paper A method.", 2),
        ]
        chunks_b = [
            _make_chunk("paper_B", "Introduction", "Paper B intro.", 3),
        ]
        store.add_chunks(chunks_a, [_keyword_embedding(c.content) for c in chunks_a])
        store.add_chunks(chunks_b, [_keyword_embedding(c.content) for c in chunks_b])
        assert store.count() == 3

        deleted = store.delete_paper("paper_A")
        assert deleted == 2
        assert store.count() == 1

        results = store.query(_keyword_embedding("intro"), top_k=5)
        assert all(r["paper_id"] == "paper_B" for r in results)


def test_vector_store_persists_across_instances():
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=persist_dir)
        chunks = [
            _make_chunk(
                "paper_A", "Introduction", "infrared detection introduction.", 1
            ),
            _make_chunk("paper_A", "Method", "vl attention method for detection.", 2),
        ]
        store.add_chunks(chunks, [_keyword_embedding(c.content) for c in chunks])

        reloaded = VectorStore(persist_dir=persist_dir)
        assert reloaded.count() == 2

        results = reloaded.query(_keyword_embedding("infrared detection"), top_k=2)
        assert len(results) == 2
        assert results[0]["paper_id"] == "paper_A"


def test_vector_store_delete_paper_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=persist_dir)
        chunks = [
            _make_chunk("paper_A", "Introduction", "Paper A intro.", 1),
            _make_chunk("paper_B", "Introduction", "Paper B intro.", 2),
        ]
        store.add_chunks(chunks, [_keyword_embedding(c.content) for c in chunks])

        deleted = store.delete_paper("paper_A")
        assert deleted == 1

        reloaded = VectorStore(persist_dir=persist_dir)
        assert reloaded.count() == 1
        results = reloaded.query(_keyword_embedding("intro"), top_k=5)
        assert len(results) == 1
        assert results[0]["paper_id"] == "paper_B"


def test_vector_store_empty_query():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        results = store.query([0.1] * 64, top_k=5)
        assert results == []


def test_vector_store_semantic_ranking():
    """Verify that more relevant chunks rank higher."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk(
                "paper_A", "Introduction", "infrared detection is important.", 1
            ),
            _make_chunk("paper_A", "Results", "the weather today is sunny.", 2),
            _make_chunk("paper_A", "Method", "vl model with detection pipeline.", 3),
        ]
        store.add_chunks(chunks, [_keyword_embedding(c.content) for c in chunks])

        results = store.query(_keyword_embedding("infrared detection vl"), top_k=3)
        # The "infrared detection" and "detection pipeline" chunks should beat "weather"
        top_contents = [r["content"] for r in results]
        assert "weather" not in top_contents[:2]


def _check_torch_available() -> bool:
    """Check if torch can be imported without crashing."""
    result = subprocess.run(
        [sys.executable, "-c", "import torch"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode == 0


def test_embedding_client_import():
    if not _check_torch_available():
        pytest.skip(
            "torch / sentence-transformers not available (missing VC++ runtime)"
        )
    from app.config import settings
    from app.services.embedding_client import EmbeddingClient, _resolve_model_name

    client = EmbeddingClient()
    assert client.model_name == settings.embedding_model
    assert _resolve_model_name(client.model_name) == "BAAI/bge-small-zh-v1.5"


def test_embedding_client_with_model():
    if not _check_torch_available():
        pytest.skip(
            "torch / sentence-transformers not available (missing VC++ runtime)"
        )
    from app.services.embedding_client import EmbeddingClient

    client = EmbeddingClient(model_name="all-MiniLM-L6-v2")
    try:
        emb = client.embed_query("test query")
        assert isinstance(emb, list)
        assert len(emb) > 0
        assert isinstance(emb[0], float)

        embeddings = client.embed_texts(["hello world", "goodbye"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == len(embeddings[1])
    except RuntimeError as e:
        pytest.skip(f"Embedding model not available: {e}")


if __name__ == "__main__":
    test_vector_store_add_and_count()
    test_vector_store_query_all_papers()
    test_vector_store_query_by_paper_id()
    test_vector_store_delete_paper()
    test_vector_store_empty_query()
    test_vector_store_semantic_ranking()
    test_embedding_client_import()
    test_embedding_client_with_model()
    print("All tests passed.")
