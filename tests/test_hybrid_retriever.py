import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.hybrid_retriever import HybridRetriever


def _setup(dense_results, sparse_results):
    vector_store = MagicMock()
    vector_store.query.return_value = dense_results
    embedding_client = MagicMock()
    embedding_client.embed_query.return_value = [0.1, 0.2]
    bm25 = MagicMock()
    bm25.search.return_value = sparse_results
    return vector_store, embedding_client, bm25


def test_hybrid_retriever_rejects_invalid_alpha():
    import pytest

    vs, ec, bm = _setup([], [])
    with pytest.raises(ValueError):
        HybridRetriever(vs, ec, bm, alpha=1.5)


def test_hybrid_retriever_merges_dense_and_sparse_results():
    dense = [
        {
            "chunk_id": "a",
            "content": "x",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 0.9,
        },
        {
            "chunk_id": "b",
            "content": "y",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 0.6,
        },
    ]
    sparse = [
        {
            "chunk_id": "b",
            "content": "y",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 3.0,
        },
        {
            "chunk_id": "c",
            "content": "z",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 1.5,
        },
    ]
    vs, ec, bm = _setup(dense, sparse)
    r = HybridRetriever(vs, ec, bm, alpha=0.5, recall_top_k=20)

    results = r.search("q", top_k=3)
    ids = [x["chunk_id"] for x in results]

    assert set(ids) == {"a", "b", "c"}
    for item in results:
        assert "dense_score" in item and "sparse_score" in item


def test_hybrid_retriever_alpha_weights_apply():
    dense = [
        {
            "chunk_id": "a",
            "content": "x",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 1.0,
        },
        {
            "chunk_id": "b",
            "content": "y",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 0.0,
        },
    ]
    sparse = [
        {
            "chunk_id": "a",
            "content": "x",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 0.0,
        },
        {
            "chunk_id": "b",
            "content": "y",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 1.0,
        },
    ]
    vs, ec, bm = _setup(dense, sparse)

    r_dense = HybridRetriever(vs, ec, bm, alpha=1.0)
    out = r_dense.search("q", top_k=2)
    assert out[0]["chunk_id"] == "a"

    r_sparse = HybridRetriever(vs, ec, bm, alpha=0.0)
    out = r_sparse.search("q", top_k=2)
    assert out[0]["chunk_id"] == "b"


def test_hybrid_retriever_empty_returns_empty():
    vs, ec, bm = _setup([], [])
    r = HybridRetriever(vs, ec, bm)
    assert r.search("q", top_k=5) == []


def test_hybrid_retriever_respects_top_k():
    dense = [
        {
            "chunk_id": f"c{i}",
            "content": "x",
            "paper_id": "p",
            "title": "t",
            "section": "s",
            "score": 1.0 - i * 0.1,
        }
        for i in range(5)
    ]
    sparse = []
    vs, ec, bm = _setup(dense, sparse)
    r = HybridRetriever(vs, ec, bm, alpha=1.0)
    out = r.search("q", top_k=2)
    assert len(out) == 2
