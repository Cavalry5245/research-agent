import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.prompts import qa_prompt
from app.prompts.qa_prompt import build_qa_prompt
from app.schemas import Chunk
from app.services.paper_qa import _build_context, answer_question
from app.services.vector_store import VectorStore

MOCK_ANSWER = (
    "该论文的核心创新点是将视觉-语言模型引入红外小目标检测，"
    "通过空间注意力与语义引导相结合，降低误报率。\n\n"
    "依据片段：[片段 1], [片段 2]"
)


def _make_chunk(paper_id: str, section: str, content: str, seq: int) -> Chunk:
    return Chunk(
        chunk_id=f"{paper_id}_chunk_{seq:04d}",
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        section=section,
        content=content,
    )


def _keyword_embedding(text: str, dim: int = 64) -> list[float]:
    import math

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
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def test_build_qa_prompt():
    prompt = build_qa_prompt("核心创新点是什么？", "[片段 1] VLM-based approach...")
    assert "核心创新点是什么？" in prompt
    assert "[片段 1]" in prompt
    assert "不要使用上下文之外的知识" in prompt
    assert "根据当前论文片段无法判断" in prompt


def test_build_query_rewrite_prompt_contains_memory_boundaries():
    prompt = qa_prompt.build_query_rewrite_prompt(
        question="How does it compare to CLIP?",
        conversation_summary="User is comparing VLM detectors for infrared targets.",
        recent_turns="User: What is the core method?\nAssistant: It uses VLM guidance.",
    )

    assert "How does it compare to CLIP?" in prompt
    assert "User is comparing VLM detectors for infrared targets." in prompt
    assert "User: What is the core method?" in prompt
    assert "CONVERSATION SUMMARY" in prompt
    assert "RECENT TURNS" in prompt
    assert "CURRENT QUESTION" in prompt
    assert "do not answer" in prompt.lower()
    assert "preserve original technical terms" in prompt.lower()


def test_build_contextual_qa_prompt_keeps_history_out_of_facts():
    prompt = qa_prompt.build_contextual_qa_prompt(
        question="What about the ablation?",
        rewritten_question="ablation study results for VLM infrared detector",
        context="[fragment 1] The ablation removes language guidance.",
        conversation_summary="User cares about method details.",
        recent_turns="User: Explain the architecture.\nAssistant: ...",
    )

    assert "What about the ablation?" in prompt
    assert "ablation study results for VLM infrared detector" in prompt
    assert "[fragment 1] The ablation removes language guidance." in prompt
    assert "User cares about method details." in prompt
    assert "User: Explain the architecture." in prompt
    assert "only retrieved paper" in prompt.lower()
    assert "evidence" in prompt.lower()
    assert "memory" in prompt.lower()
    assert "intent" in prompt.lower()
    assert "not factual support" in prompt.lower()


def test_build_summary_update_prompt_warns_against_fact_memory():
    prompt = qa_prompt.build_summary_update_prompt(
        existing_summary="User prefers concise answers with evidence fragments.",
        recent_turns="User: What is the accuracy?\nAssistant: The paper reports 91%.",
    )

    assert "User prefers concise answers with evidence fragments." in prompt
    assert "User: What is the accuracy?" in prompt
    assert "EXISTING SUMMARY" in prompt
    assert "RECENT QA TURNS" in prompt
    assert "do not store" in prompt.lower()
    assert "paper factual claims" in prompt.lower()
    assert "durable memory" in prompt.lower()
    assert "query rewriting" in prompt.lower()


def test_build_context():
    results = [
        {
            "paper_id": "p1",
            "title": "T1",
            "section": "Method",
            "content": "Method content.",
        },
        {
            "paper_id": "p2",
            "title": "T2",
            "section": "Experiments",
            "content": "Experiment content.",
        },
    ]
    ctx = _build_context(results)
    # New format: [paper_id p.page section]
    assert "[p1 p.? Method]" in ctx
    assert "[p2 p.? Experiments]" in ctx
    assert "Method content." in ctx
    assert "Experiment content." in ctx
    assert "---" in ctx  # Separator between chunks


def test_answer_question_with_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk(
                "paper_A", "Method", "We propose a vl attention detection method.", 1
            ),
            _make_chunk(
                "paper_A", "Experiments", "The infrared detection achieves SOTA.", 2
            ),
            _make_chunk("paper_B", "Introduction", "Model compression survey.", 3),
        ]
        chunks[0].page_number = 2
        chunks[0].chunk_start = 0
        chunks[0].chunk_end = len(chunks[0].content)
        chunks[1].page_number = 3
        chunks[1].chunk_start = 10
        chunks[1].chunk_end = 10 + len(chunks[1].content)
        store.add_chunks(chunks, [_keyword_embedding(c.content) for c in chunks])

        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = _keyword_embedding(
            "infrared detection method"
        )

        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = MOCK_ANSWER

        result = answer_question(
            question="核心创新点是什么？",
            vector_store=store,
            embedding_client=mock_emb,
            llm_client=mock_llm,
            top_k=2,
        )

        assert result["question"] == "核心创新点是什么？"
        assert MOCK_ANSWER in result["answer"]
        assert len(result["sources"]) == 2

        source_contents = [s["content"] for s in result["sources"]]
        assert any("vl attention" in c for c in source_contents)
        assert any("SOTA" in c for c in source_contents)

        for s in result["sources"]:
            assert s["paper_id"] == "paper_A"
            assert s["chunk_id"]
            assert s["section"]
            assert s["page_number"] is not None
            assert s["chunk_start"] is not None
            assert s["chunk_end"] is not None

        mock_emb.embed_query.assert_called_once_with("核心创新点是什么？")


def test_answer_question_filter_by_paper_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk("paper_A", "Method", "vl attention detection method.", 1),
            _make_chunk("paper_B", "Method", "model compression pruning.", 2),
        ]
        store.add_chunks(chunks, [_keyword_embedding(c.content) for c in chunks])

        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = _keyword_embedding("detection")

        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "基于检索结果..."

        result = answer_question(
            question="方法是什么？",
            vector_store=store,
            embedding_client=mock_emb,
            llm_client=mock_llm,
            paper_id="paper_A",
            top_k=5,
        )

        assert len(result["sources"]) == 1
        assert result["sources"][0]["paper_id"] == "paper_A"


def test_answer_question_empty_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))

        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.1] * 64

        mock_llm = MagicMock()

        result = answer_question(
            question="核心创新点？",
            vector_store=store,
            embedding_client=mock_emb,
            llm_client=mock_llm,
        )

        assert "没有检索到相关内容" in result["answer"]
        assert result["sources"] == []
        mock_llm.generate_text.assert_not_called()


def test_answer_question_prompt_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        store.add_chunks(
            [_make_chunk("paper_A", "Method", "VLM detection method.", 1)],
            [_keyword_embedding("VLM detection method.")],
        )

        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = _keyword_embedding("VLM detection")

        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "answer"

        answer_question(
            question="方法？",
            vector_store=store,
            embedding_client=mock_emb,
            llm_client=mock_llm,
        )

        call_prompt = mock_llm.generate_text.call_args[0][0]
        assert "方法？" in call_prompt
        assert "根据当前论文片段无法判断" in call_prompt
        assert "VLM detection method" in call_prompt


def test_answer_question_uses_reranked_results_for_prompt_and_sources():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        chunks = [
            _make_chunk("paper_A", "Method", "dense first chunk", 1),
            _make_chunk("paper_A", "Conclusion", "dense second chunk", 2),
        ]
        store.add_chunks(chunks, [[1.0, 0.0], [0.9, 0.1]])

        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [1.0, 0.0]

        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "reranked answer"

        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [
            {
                "chunk_id": "paper_A_chunk_0002",
                "content": "dense second chunk",
                "paper_id": "paper_A",
                "title": "Paper paper_A",
                "section": "Conclusion",
                "score": 0.2,
                "rerank_score": 0.99,
            },
            {
                "chunk_id": "paper_A_chunk_0001",
                "content": "dense first chunk",
                "paper_id": "paper_A",
                "title": "Paper paper_A",
                "section": "Method",
                "score": 1.0,
                "rerank_score": 0.5,
            },
        ]

        result = answer_question(
            question="哪个结论最重要？",
            vector_store=store,
            embedding_client=mock_emb,
            llm_client=mock_llm,
            top_k=2,
            reranker=mock_reranker,
        )

        mock_reranker.rerank.assert_called_once()
        rerank_kwargs = mock_reranker.rerank.call_args.kwargs
        assert rerank_kwargs["question"] == "哪个结论最重要？"
        assert [item["chunk_id"] for item in rerank_kwargs["results"]] == [
            "paper_A_chunk_0001",
            "paper_A_chunk_0002",
        ]
        prompt = mock_llm.generate_text.call_args[0][0]
        assert prompt.index("dense second chunk") < prompt.index("dense first chunk")
        assert [source["chunk_id"] for source in result["sources"]] == [
            "paper_A_chunk_0002",
            "paper_A_chunk_0001",
        ]
        assert result["sources"][0]["score"] == pytest.approx(0.99)


def test_answer_question_validates_reranker_output_length():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        store.add_chunks(
            [_make_chunk("paper_A", "Method", "dense chunk", 1)],
            [[1.0, 0.0]],
        )

        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [1.0, 0.0]

        mock_llm = MagicMock()
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = []

        with pytest.raises(ValueError, match="reranker returned empty results"):
            answer_question(
                question="方法是什么？",
                vector_store=store,
                embedding_client=mock_emb,
                llm_client=mock_llm,
                reranker=mock_reranker,
            )

        mock_llm.generate_text.assert_not_called()


if __name__ == "__main__":
    test_build_qa_prompt()
    test_build_context()
    test_answer_question_with_results()
    test_answer_question_filter_by_paper_id()
    test_answer_question_empty_store()
    test_answer_question_prompt_content()
    print("All tests passed.")
