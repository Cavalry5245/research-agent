import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.bm25_retriever import BM25Retriever, tokenize_zh


def _fake_vector_store(chunks: list[dict]):
    store = MagicMock()
    store.list_chunks.return_value = chunks
    return store


def test_tokenize_zh_returns_tokens():
    tokens = tokenize_zh("多模态大模型对比")
    assert any(t in tokens for t in ["多", "模态", "模型", "多模态"])
    assert "" not in tokens


def test_bm25_retriever_returns_results_for_matching_query():
    chunks = [
        {"chunk_id": "a", "content": "卷积神经网络在图像识别中表现优异", "paper_id": "p1", "title": "t", "section": "s"},
        {"chunk_id": "b", "content": "强化学习用于机器人控制", "paper_id": "p1", "title": "t", "section": "s"},
        {"chunk_id": "c", "content": "图像识别的卷积模型对比", "paper_id": "p1", "title": "t", "section": "s"},
    ]
    retriever = BM25Retriever(_fake_vector_store(chunks))
    results = retriever.search("卷积 图像识别", top_k=2)

    assert len(results) == 2
    ids = [r["chunk_id"] for r in results]
    assert "b" not in ids
    assert results[0]["score"] >= results[1]["score"]


def test_bm25_retriever_handles_empty_corpus():
    retriever = BM25Retriever(_fake_vector_store([]))
    assert retriever.search("无", top_k=5) == []


def test_bm25_retriever_filters_by_paper_id_via_vector_store():
    chunks_p2 = [
        {"chunk_id": "x", "content": "transformer attention", "paper_id": "p2", "title": "t", "section": "s"},
    ]
    store = MagicMock()
    store.list_chunks.return_value = chunks_p2
    retriever = BM25Retriever(store)

    results = retriever.search("transformer", top_k=1, paper_id="p2")

    store.list_chunks.assert_called_with(paper_id="p2")
    assert len(results) == 1
    assert results[0]["paper_id"] == "p2"


def test_bm25_retriever_preserves_all_fields_in_results():
    chunks = [
        {"chunk_id": "c1", "content": "深度学习入门", "paper_id": "p1", "title": "Intro", "section": "1", "page_number": 3, "chunk_start": 0, "chunk_end": 100},
    ]
    retriever = BM25Retriever(_fake_vector_store(chunks))
    results = retriever.search("深度学习", top_k=1)

    assert results[0]["title"] == "Intro"
    assert results[0]["page_number"] == 3
    assert results[0]["chunk_start"] == 0
