"""Tests for the memory subsystem: short-term, long-term, and semantic memory."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.memory.long_term import LongTermMemory
from app.agents.memory.semantic import SemanticMemory
from app.agents.memory.short_term import ShortTermMemory
from app.services.memory_store import MemoryStore


def _make_store():
    return MemoryStore(":memory:")


# ── ShortTermMemory ──────────────────────────────────────────────────────────


class TestShortTerm:
    def test_create_and_retrieve_messages(self):
        store = _make_store()
        stm = ShortTermMemory(store, max_messages=10)
        cid = stm.create_conversation("test conv")
        stm.add_message(cid, "user", "hello")
        stm.add_message(cid, "assistant", "hi there")

        ctx = stm.get_context(cid)
        assert len(ctx) == 2
        assert ctx[0] == {"role": "user", "content": "hello"}
        assert ctx[1] == {"role": "assistant", "content": "hi there"}

    def test_sliding_window_truncation(self):
        store = _make_store()
        stm = ShortTermMemory(store, max_messages=3)
        cid = stm.create_conversation("truncation test")

        for i in range(5):
            stm.add_message(cid, "user", f"msg-{i}")

        ctx = stm.get_context(cid)
        assert len(ctx) == 3
        assert ctx[0]["content"] == "msg-2"
        assert ctx[2]["content"] == "msg-4"

    def test_empty_conversation_returns_empty_context(self):
        store = _make_store()
        stm = ShortTermMemory(store, max_messages=10)
        cid = stm.create_conversation()
        assert stm.get_context(cid) == []


# ── LongTermMemory ───────────────────────────────────────────────────────────


class TestLongTerm:
    def test_preferences_crud(self):
        store = _make_store()
        ltm = LongTermMemory(store)

        ltm.set_preference("language", "zh")
        ltm.set_preference("theme", "dark")
        assert ltm.get_preference("language") == "zh"
        assert ltm.get_preference("nonexistent") is None
        assert ltm.get_all_preferences() == {"language": "zh", "theme": "dark"}

    def test_preference_overwrite(self):
        store = _make_store()
        ltm = LongTermMemory(store)
        ltm.set_preference("k", "v1")
        ltm.set_preference("k", "v2")
        assert ltm.get_preference("k") == "v2"

    def test_reading_history(self):
        store = _make_store()
        ltm = LongTermMemory(store)

        ltm.record_reading("paper-1", "view")
        ltm.record_reading("paper-2", "note_generated")
        ltm.record_reading("paper-1", "qa")

        history = ltm.get_reading_history(limit=10)
        assert len(history) == 3
        assert history[0]["paper_id"] == "paper-1"  # most recent first

        paper1_history = ltm.get_reading_history(paper_id="paper-1")
        assert len(paper1_history) == 2

    def test_recently_read_papers_deduplicates(self):
        store = _make_store()
        ltm = LongTermMemory(store)
        ltm.record_reading("paper-1", "view")
        ltm.record_reading("paper-2", "view")
        ltm.record_reading("paper-1", "qa")

        recent = ltm.get_recently_read_papers(limit=5)
        assert recent == ["paper-1", "paper-2"]

    def test_frequent_questions(self):
        store = _make_store()
        ltm = LongTermMemory(store)
        ltm.record_question("What is RAG?", "paper-1")
        ltm.record_question("What is RAG?", "paper-2")
        ltm.record_question("How does rerank work?")

        top = ltm.get_frequent_questions(top_k=2)
        assert top[0] == ("What is RAG?", 2)
        assert top[1] == ("How does rerank work?", 1)


# ── SemanticMemory ───────────────────────────────────────────────────────────


class _FakeEmbeddingClient:
    """Deterministic embedding for testing: uses character frequency vector."""

    def embed_query(self, text: str) -> list[float]:
        vec = [0.0] * 26
        for ch in text.lower():
            if "a" <= ch <= "z":
                vec[ord(ch) - ord("a")] += 1.0
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]


class TestSemantic:
    def test_store_and_recall(self):
        store = _make_store()
        ec = _FakeEmbeddingClient()
        sm = SemanticMemory(store, embedding_client=ec)

        sm.store_fact("RAG uses retrieval augmented generation")
        sm.store_fact("Reranking improves precision of search results")
        sm.store_fact("Python is a programming language")

        results = sm.recall("retrieval and generation", top_k=2)
        assert len(results) == 2
        assert (
            "RAG" in results[0]["content"]
            or "retrieval" in results[0]["content"].lower()
        )

    def test_delete_fact(self):
        store = _make_store()
        ec = _FakeEmbeddingClient()
        sm = SemanticMemory(store, embedding_client=ec)

        fid = sm.store_fact("temporary fact")
        assert sm.delete_fact(fid) is True
        assert sm.recall("temporary", top_k=5) == []

    def test_empty_recall(self):
        store = _make_store()
        ec = _FakeEmbeddingClient()
        sm = SemanticMemory(store, embedding_client=ec)
        assert sm.recall("anything", top_k=3) == []
