import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk
from app.services.paper_qa import answer_question
from app.services.vector_store import VectorStore


class ClosedClientError(RuntimeError):
    pass


class FlakyLLM:
    def generate_text(self, prompt: str) -> str:
        raise ClosedClientError("Cannot send a request, as the client has been closed.")


class FakeEmbedding:
    def embed_query(self, query: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def _make_chunk() -> Chunk:
    return Chunk(
        chunk_id="paper_A_chunk_0001",
        paper_id="paper_A",
        title="Paper A",
        section="Method",
        content="method content",
    )


def test_answer_question_recovers_with_fresh_llm_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        store.add_chunks([_make_chunk()], [[1.0, 0.0, 0.0]])

        recovered_llm = MagicMock()
        recovered_llm.generate_text.return_value = "恢复后的回答"
        llm_factory = MagicMock(return_value=recovered_llm)

        result = answer_question(
            question="方法是什么？",
            vector_store=store,
            embedding_client=FakeEmbedding(),
            llm_client=FlakyLLM(),
            llm_client_factory=llm_factory,
        )

        assert result["answer"] == "恢复后的回答"
        llm_factory.assert_called_once_with()
        recovered_llm.generate_text.assert_called_once()


def test_answer_question_uses_default_llm_factory_when_not_provided():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        store.add_chunks([_make_chunk()], [[1.0, 0.0, 0.0]])

        recovered_llm = MagicMock()
        recovered_llm.generate_text.return_value = "默认工厂恢复"

        with patch("app.services.paper_qa.LLMClient", return_value=recovered_llm):
            result = answer_question(
                question="方法是什么？",
                vector_store=store,
                embedding_client=FakeEmbedding(),
                llm_client=FlakyLLM(),
            )

        assert result["answer"] == "默认工厂恢复"
        recovered_llm.generate_text.assert_called_once()


def test_answer_question_does_not_swallow_other_runtime_errors():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        store.add_chunks([_make_chunk()], [[1.0, 0.0, 0.0]])

        llm = MagicMock()
        llm.generate_text.side_effect = RuntimeError("upstream 503")

        with pytest.raises(RuntimeError, match="upstream 503"):
            answer_question(
                question="方法是什么？",
                vector_store=store,
                embedding_client=FakeEmbedding(),
                llm_client=llm,
            )
