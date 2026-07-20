import os
import sys
import tempfile
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk
from app.services.reranker import HybridReranker
from app.services.vector_backends.json_backend import JsonVectorBackend
from app.services.vector_store import VectorStore


def _make_chunk(paper_id: str, section: str, content: str, seq: int) -> Chunk:
    return Chunk(
        chunk_id=f"{paper_id}_chunk_{seq:04d}",
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        section=section,
        content=content,
    )


def test_identity_reranker_preserves_order_and_adds_rerank_score():
    from app.services.reranker import IdentityReranker

    reranker = IdentityReranker()
    results = [
        {"chunk_id": "c1", "score": 0.8, "content": "first"},
        {"chunk_id": "c2", "score": 0.4, "content": "second"},
    ]

    reranked = reranker.rerank(question="what matters", results=results)

    assert [item["chunk_id"] for item in reranked] == ["c1", "c2"]
    assert reranked[0]["rerank_score"] == 0.8
    assert reranked[1]["rerank_score"] == 0.4
    assert "rerank_score" not in results[0]


def test_identity_reranker_respects_top_k():
    from app.services.reranker import IdentityReranker

    reranker = IdentityReranker()
    results = [
        {"chunk_id": "c1", "score": 0.8},
        {"chunk_id": "c2", "score": 0.4},
    ]

    reranked = reranker.rerank(question="what matters", results=results, top_k=1)

    assert [item["chunk_id"] for item in reranked] == ["c1"]


def test_hybrid_reranker_promotes_keyword_dense_tie():
    reranker = HybridReranker(alpha=0.2)
    results = [
        {"chunk_id": "c1", "score": 0.9, "content": "generic context only"},
        {
            "chunk_id": "c2",
            "score": 0.9,
            "content": "infrared detection benchmark details",
        },
    ]

    reranked = reranker.rerank(question="infrared detection", results=results)

    assert [item["chunk_id"] for item in reranked] == ["c2", "c1"]
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]


def test_hybrid_reranker_respects_top_k_and_preserves_original_score():
    reranker = HybridReranker(alpha=0.5)
    results = [
        {"chunk_id": "c1", "score": 0.3, "content": "attention attention"},
        {"chunk_id": "c2", "score": 0.7, "content": "attention model experiments"},
    ]

    reranked = reranker.rerank(question="attention model", results=results, top_k=1)

    assert len(reranked) == 1
    assert reranked[0]["chunk_id"] == "c2"
    assert reranked[0]["score"] == 0.7
    assert "rerank_score" in reranked[0]


def test_vector_store_hybrid_query_uses_question_text_to_reorder_dense_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))
        chunks = [
            _make_chunk("paper_A", "Method", "generic context only", 1),
            _make_chunk(
                "paper_A", "Experiments", "infrared detection benchmark details", 2
            ),
        ]
        store.add_chunks(chunks, [[1.0, 0.0], [1.0, 0.0]])

        results = store.query(
            [1.0, 0.0], top_k=2, hybrid_query_text="infrared detection"
        )

        assert [item["chunk_id"] for item in results] == [
            "paper_A_chunk_0002",
            "paper_A_chunk_0001",
        ]
        assert results[0]["score"] > results[1]["score"]


def test_cross_encoder_reranker_reorders_by_predict_scores():
    from app.services.reranker import CrossEncoderReranker

    fake_model = MagicMock()
    fake_model.predict.return_value = [0.1, 0.95, 0.5]
    reranker = CrossEncoderReranker(model=fake_model)
    results = [
        {"chunk_id": "c1", "score": 0.8, "content": "alpha"},
        {"chunk_id": "c2", "score": 0.4, "content": "beta"},
        {"chunk_id": "c3", "score": 0.6, "content": "gamma"},
    ]

    reranked = reranker.rerank(question="q", results=results)

    assert [item["chunk_id"] for item in reranked] == ["c2", "c3", "c1"]
    assert reranked[0]["rerank_score"] == 0.95
    fake_model.predict.assert_called_once()


def test_cross_encoder_reranker_respects_top_k_and_handles_empty():
    from app.services.reranker import CrossEncoderReranker

    fake_model = MagicMock()
    fake_model.predict.return_value = [0.2, 0.9]
    reranker = CrossEncoderReranker(model=fake_model)
    results = [
        {"chunk_id": "c1", "score": 0.5, "content": "a"},
        {"chunk_id": "c2", "score": 0.5, "content": "b"},
    ]

    reranked = reranker.rerank(question="q", results=results, top_k=1)
    assert len(reranked) == 1
    assert reranked[0]["chunk_id"] == "c2"

    empty = reranker.rerank(question="q", results=[], top_k=5)
    assert empty == []


def test_cross_encoder_reranker_lazy_loads_model():
    from app.services.reranker import CrossEncoderReranker

    reranker = CrossEncoderReranker(model_name="dummy")
    assert reranker._model is None
