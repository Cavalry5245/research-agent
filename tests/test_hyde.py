import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.hyde import HyDE


def _setup():
    llm = MagicMock()
    llm.generate_text.return_value = "卷积神经网络在 ImageNet 上达到 SOTA..."
    embedding = MagicMock()
    embedding.embed_query.return_value = [0.1, 0.2, 0.3]
    vector_store = MagicMock()
    vector_store.query.return_value = [
        {"chunk_id": "c1", "content": "x", "paper_id": "p", "title": "t", "section": "s", "score": 0.9},
    ]
    return llm, embedding, vector_store


def test_hyde_generates_hypothetical_doc_and_searches():
    llm, embedding, vs = _setup()
    hyde = HyDE(llm, embedding, vs)

    results = hyde.search("CNN 在图像分类上效果如何", top_k=1)

    llm.generate_text.assert_called_once()
    embedding.embed_query.assert_called_once_with("卷积神经网络在 ImageNet 上达到 SOTA...")
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c1"


def test_hyde_falls_back_to_query_on_llm_failure():
    llm, embedding, vs = _setup()
    llm.generate_text.side_effect = RuntimeError("LLM down")
    hyde = HyDE(llm, embedding, vs)

    hyde.search("原始查询", top_k=1)

    embedding.embed_query.assert_called_once_with("原始查询")


def test_hyde_passes_paper_id_to_vector_store():
    llm, embedding, vs = _setup()
    hyde = HyDE(llm, embedding, vs)

    hyde.search("q", top_k=3, paper_id="paper_X")

    vs.query.assert_called_once()
    assert vs.query.call_args.kwargs["paper_id"] == "paper_X"
    assert vs.query.call_args.kwargs["top_k"] == 3
