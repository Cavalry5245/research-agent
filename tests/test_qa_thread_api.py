import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app
from app.routers.conversations import set_memory_store
from app.services.memory_store import MemoryStore


def _qa_payload(answer="grounded answer"):
    return {
        "question": "rewritten question",
        "answer": answer,
        "sources": [
            {
                "paper_id": "paper_001",
                "title": "Grounding DINO",
                "section": "Results",
                "chunk_id": "chunk_1",
                "content": "52.5 AP on COCO zero-shot.",
                "score": 0.9,
            }
        ],
        "retrieval_time": 0.1,
        "llm_time": 0.2,
    }


def test_qa_endpoint_creates_conversation_and_returns_thread_fields(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)
    llm = MagicMock()
    llm.generate_text.return_value = "Grounding DINO zero-shot metrics?"

    try:
        with patch("app.main._get_llm_client", return_value=llm), patch(
            "app.main.answer_question", return_value=_qa_payload()
        ) as mock_answer:
            resp = client.post(
                "/qa",
                json={
                    "question": "它的 zero-shot 指标是多少？",
                    "paper_id": "paper_001",
                    "top_k": 5,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"]
        assert data["question"] == "它的 zero-shot 指标是多少？"
        assert data["rewritten_question"] == "Grounding DINO zero-shot metrics?"
        assert data["answer"] == "grounded answer"
        mock_answer.assert_called_once()
        assert mock_answer.call_args.kwargs["question"] == (
            "Grounding DINO zero-shot metrics?"
        )
        assert store.count_messages(data["conversation_id"]) == 2
    finally:
        set_memory_store(None)
        store.close()


def test_qa_endpoint_reuses_conversation_id(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)
    llm = MagicMock()
    llm.generate_text.side_effect = ["First rewritten", "Second rewritten"]

    try:
        with patch("app.main._get_llm_client", return_value=llm), patch(
            "app.main.answer_question", return_value=_qa_payload()
        ):
            first = client.post("/qa", json={"question": "First?", "top_k": 5}).json()
            second = client.post(
                "/qa",
                json={
                    "question": "它呢？",
                    "top_k": 5,
                    "conversation_id": first["conversation_id"],
                },
            ).json()

        assert second["conversation_id"] == first["conversation_id"]
        assert second["rewritten_question"] == "Second rewritten"
        assert store.count_messages(first["conversation_id"]) == 4

        # The second rewrite prompt must see the first turn's context so
        # coreference ("它呢？") can be resolved against prior messages.
        second_rewrite_prompt = llm.generate_text.call_args_list[1].args[0]
        assert "First?" in second_rewrite_prompt
        assert "First rewritten" in second_rewrite_prompt
    finally:
        set_memory_store(None)
        store.close()


def test_qa_endpoint_survives_rewrite_failure(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)
    llm = MagicMock()
    llm.generate_text.side_effect = RuntimeError("llm down")

    try:
        with patch("app.main._get_llm_client", return_value=llm), patch(
            "app.main.answer_question", return_value=_qa_payload()
        ) as mock_answer:
            resp = client.post(
                "/qa",
                json={"question": "原始问题？", "paper_id": "paper_001", "top_k": 5},
            )

        assert resp.status_code == 200
        data = resp.json()
        # Rewrite failed → falls back to the original question for retrieval.
        assert data["rewritten_question"] == "原始问题？"
        assert data["answer"] == "grounded answer"
        assert mock_answer.call_args.kwargs["question"] == "原始问题？"
    finally:
        set_memory_store(None)
        store.close()


def test_qa_endpoint_rejects_deleted_conversation(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)

    try:
        resp = client.post(
            "/qa",
            json={"question": "Follow up?", "conversation_id": "missing"},
        )

        assert resp.status_code == 404
    finally:
        set_memory_store(None)
        store.close()


def test_qa_endpoint_rejects_non_qa_conversation(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)
    other_id = store.create_conversation(
        title="Notes chat", metadata='{"kind": "notes"}'
    )

    try:
        resp = client.post(
            "/qa",
            json={"question": "Anything?", "conversation_id": other_id},
        )

        assert resp.status_code == 400
        assert "not a QA conversation" in resp.json()["message"]
    finally:
        set_memory_store(None)
        store.close()
