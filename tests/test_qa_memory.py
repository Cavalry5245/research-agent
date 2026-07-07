import json
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.memory_store import MemoryStore
from app.services.qa_memory import QAMemoryService


class FakeLLM:
    def __init__(self, responses=None, fail_on_calls=None):
        self.responses = list(responses or [])
        self.fail_on_calls = set(fail_on_calls or [])
        self.calls = []

    def generate_text(self, prompt):
        self.calls.append(prompt)
        if len(self.calls) in self.fail_on_calls:
            raise RuntimeError("llm failed")
        if self.responses:
            return self.responses.pop(0)
        return ""


def _metadata(row):
    return json.loads(row["metadata"])


def _make_service(tmp_path, llm_client=None, **kwargs):
    store = MemoryStore(tmp_path / "qa_memory.db")
    service = QAMemoryService(store=store, llm_client=llm_client, **kwargs)
    return service, store


def test_ask_creates_qa_conversation_and_persists_messages(tmp_path):
    llm = FakeLLM(["rewritten retrieval query"])
    service, store = _make_service(tmp_path, llm_client=llm)

    def answer_fn(**kwargs):
        assert kwargs == {
            "question": "rewritten retrieval query",
            "paper_id": "paper-1",
            "top_k": 3,
            "conversation_summary": "",
            "recent_turns": "",
            "original_question": "What is the method?",
        }
        return {
            "answer": "The method is retrieval augmented QA.",
            "sources": [{"chunk_id": "c1"}],
            "retrieval_time": 0.1,
            "llm_time": 0.2,
        }

    result = service.ask(
        "What is the method?", answer_fn, paper_id="paper-1", top_k=3
    )

    assert result["conversation_id"]
    assert result["question"] == "What is the method?"
    assert result["rewritten_question"] == "rewritten retrieval query"
    assert result["rewrite_failed"] is False
    assert result["answer"] == "The method is retrieval augmented QA."

    conversation = store.get_conversation(result["conversation_id"])
    conv_meta = _metadata(conversation)
    assert conv_meta["kind"] == "qa"
    assert conv_meta["default_paper_id"] == "paper-1"
    assert conv_meta["summary"] == ""
    assert conv_meta["summary_message_count"] == 0
    assert conv_meta["last_rewritten_question"] == "rewritten retrieval query"
    assert conversation["title"] == "What is the method?"

    messages = store.get_messages(result["conversation_id"])
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What is the method?"
    assert _metadata(messages[0]) == {
        "kind": "qa_user",
        "paper_id": "paper-1",
        "top_k": 3,
    }
    assistant_meta = _metadata(messages[1])
    assert assistant_meta["kind"] == "qa_assistant"
    assert assistant_meta["status"] == "done"
    assert assistant_meta["paper_id"] == "paper-1"
    assert assistant_meta["top_k"] == 3
    assert assistant_meta["rewritten_question"] == "rewritten retrieval query"
    assert assistant_meta["sources"] == [{"chunk_id": "c1"}]
    assert assistant_meta["retrieval_time"] == 0.1
    assert assistant_meta["llm_time"] == 0.2
    assert assistant_meta["rewrite_failed"] is False


def test_ask_reuses_existing_qa_conversation_and_includes_recent_turns(tmp_path):
    llm = FakeLLM(["standalone follow up query"])
    service, store = _make_service(tmp_path, llm_client=llm, recent_message_limit=4)
    conv_id = store.create_conversation(
        title="Existing QA",
        metadata=json.dumps(
            {
                "kind": "qa",
                "default_paper_id": "paper-1",
                "summary": "User is asking about the model architecture.",
                "summary_message_count": 2,
                "last_rewritten_question": "Previous rewritten query",
            }
        ),
    )
    store.add_message(conv_id, "user", "What is the encoder?")
    store.add_message(conv_id, "assistant", "It uses a transformer encoder.")

    def answer_fn(**kwargs):
        assert kwargs["question"] == "standalone follow up query"
        assert kwargs["paper_id"] == "paper-2"
        assert kwargs["top_k"] == 7
        assert kwargs["conversation_summary"] == (
            "User is asking about the model architecture."
        )
        assert kwargs["recent_turns"] == (
            "user: What is the encoder?\n"
            "assistant: It uses a transformer encoder."
        )
        assert kwargs["original_question"] == "How is it trained?"
        assert kwargs["extra_flag"] is True
        return {"answer": "It is trained contrastively.", "sources": ["s1"]}

    result = service.ask(
        "How is it trained?",
        answer_fn,
        paper_id="paper-2",
        top_k=7,
        conversation_id=conv_id,
        extra_flag=True,
    )

    assert result["conversation_id"] == conv_id
    assert result["question"] == "How is it trained?"
    assert result["rewritten_question"] == "standalone follow up query"
    rewrite_prompt = llm.calls[0]
    assert "User is asking about the model architecture." in rewrite_prompt
    assert "user: What is the encoder?" in rewrite_prompt
    # previous_rewritten_question and paper_id are fed into the rewrite prompt
    assert "上一轮改写问题" in rewrite_prompt
    assert "Previous rewritten query" in rewrite_prompt
    assert "当前论文范围" in rewrite_prompt
    assert "paper-2" in rewrite_prompt

    messages = store.get_messages(conv_id)
    assert len(messages) == 4
    assert messages[-2]["content"] == "How is it trained?"
    assert messages[-1]["content"] == "It is trained contrastively."
    conv_meta = _metadata(store.get_conversation(conv_id))
    assert conv_meta["default_paper_id"] == "paper-2"
    assert conv_meta["last_rewritten_question"] == "standalone follow up query"


def test_ask_preserves_default_paper_id_on_scopeless_followup(tmp_path):
    llm = FakeLLM(["rewritten q1", "rewritten q2"])
    service, store = _make_service(tmp_path, llm_client=llm)

    def answer_fn(**kwargs):
        return {"answer": "a", "sources": []}

    first = service.ask("First?", answer_fn, paper_id="paper-1")
    conv_id = first["conversation_id"]
    assert _metadata(store.get_conversation(conv_id))["default_paper_id"] == "paper-1"

    # Follow-up carries no paper_id; default_paper_id must be preserved, not clobbered to None.
    service.ask("它呢？", answer_fn, conversation_id=conv_id)

    conv_meta = _metadata(store.get_conversation(conv_id))
    assert conv_meta["default_paper_id"] == "paper-1"
    assert conv_meta["last_rewritten_question"] == "rewritten q2"


def test_ask_rejects_missing_conversation_id(tmp_path):
    service, _store = _make_service(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        service.ask("Question?", lambda **_: {"answer": "", "sources": []}, conversation_id="missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Conversation not found"


def test_ask_rejects_non_qa_conversation(tmp_path):
    service, store = _make_service(tmp_path)
    conv_id = store.create_conversation(
        title="Other", metadata=json.dumps({"kind": "notes"})
    )

    with pytest.raises(HTTPException) as exc_info:
        service.ask("Question?", lambda **_: {"answer": "", "sources": []}, conversation_id=conv_id)

    assert exc_info.value.status_code == 400
    assert "not a QA conversation" in exc_info.value.detail


def test_ask_records_error_message_when_answer_fn_raises(tmp_path):
    llm = FakeLLM(["rewritten q"])
    service, store = _make_service(tmp_path, llm_client=llm)

    def answer_fn(**kwargs):
        raise RuntimeError("upstream LLM blew up")

    with pytest.raises(RuntimeError, match="upstream LLM blew up"):
        service.ask("Q?", answer_fn, paper_id="paper-1")

    messages = store.get_messages(store.list_conversations_by_kind("qa")[0]["id"])
    assistant_meta = _metadata(messages[-1])
    assert assistant_meta["kind"] == "qa_assistant"
    assert assistant_meta["status"] == "error"
    assert assistant_meta["error"] == "upstream LLM blew up"
    # content carries the error message so the UI doesn't render an empty bubble
    assert messages[-1]["content"] == "upstream LLM blew up"
    assert assistant_meta["rewritten_question"] == "rewritten q"


def test_ask_includes_rewritten_annotation_in_recent_turns(tmp_path):
    llm = FakeLLM(["rewritten follow up"])
    service, store = _make_service(tmp_path, llm_client=llm, recent_message_limit=4)
    conv_id = store.create_conversation(
        title="Existing QA",
        metadata=json.dumps({"kind": "qa", "summary_message_count": 0}),
    )
    # Prior assistant turn carries a rewritten_question in metadata.
    store.add_message(
        conv_id,
        "assistant",
        "It uses a transformer encoder.",
        metadata=json.dumps({"rewritten_question": "encoder architecture"}),
    )

    def answer_fn(**kwargs):
        return {"answer": "ok", "sources": []}

    service.ask("它呢？", answer_fn, conversation_id=conv_id)

    rewrite_prompt = llm.calls[0]
    assert "(rewritten: encoder architecture)" in rewrite_prompt


def test_rewrite_failure_uses_original_question_and_records_metadata(tmp_path):
    llm = FakeLLM(fail_on_calls={1})
    service, store = _make_service(tmp_path, llm_client=llm)

    def answer_fn(**kwargs):
        assert kwargs["question"] == "Original follow up?"
        return {"answer": "Fallback answer", "sources": []}

    result = service.ask("Original follow up?", answer_fn, paper_id="paper-1")

    assert result["rewritten_question"] == "Original follow up?"
    assert result["rewrite_failed"] is True
    messages = store.get_messages(result["conversation_id"])
    assistant_meta = _metadata(messages[-1])
    assert assistant_meta["rewrite_failed"] is True
    assert assistant_meta["rewritten_question"] == "Original follow up?"


def test_summary_update_runs_after_threshold_and_failure_does_not_block(tmp_path):
    llm = FakeLLM(["rewritten q1", "updated summary", "rewritten q2"], fail_on_calls={4})
    service, store = _make_service(
        tmp_path,
        llm_client=llm,
        recent_message_limit=8,
        summary_message_threshold=2,
        summary_min_new_messages=2,
    )

    def answer_fn(**kwargs):
        return {
            "answer": f"Answer for {kwargs['original_question']}",
            "sources": [{"id": kwargs["original_question"]}],
        }

    first = service.ask("Q1", answer_fn, paper_id="paper-1")
    conv_meta = _metadata(store.get_conversation(first["conversation_id"]))
    assert conv_meta["summary"] == "updated summary"
    assert conv_meta["summary_message_count"] == 2
    assert conv_meta["summary_updated_at"] is not None
    summary_prompt = llm.calls[1]
    assert "user: Q1" in summary_prompt
    assert "assistant: Answer for Q1" in summary_prompt
    # rewritten_question and source_notes are fed into the summary prompt
    assert "本轮改写问题" in summary_prompt
    assert "rewritten q1" in summary_prompt
    assert "本轮来源提示" in summary_prompt

    second = service.ask(
        "Q2", answer_fn, paper_id="paper-1", conversation_id=first["conversation_id"]
    )

    assert second["answer"] == "Answer for Q2"
    conv_meta = _metadata(store.get_conversation(first["conversation_id"]))
    assert conv_meta["summary"] == "updated summary"
    assert conv_meta["summary_message_count"] == 2
    assert len(store.get_messages(first["conversation_id"])) == 4
