"""QA conversation memory orchestration."""

import json
import time
from typing import Any, Callable

from fastapi import HTTPException

from app.prompts.qa_prompt import (
    build_query_rewrite_prompt,
    build_summary_update_prompt,
)
from app.services.memory_store import MemoryStore, parse_metadata


class QAMemoryService:
    """Manage persistent memory around paper QA turns."""

    def __init__(
        self,
        store: MemoryStore | None = None,
        llm_client: Any | None = None,
        recent_message_limit: int = 8,
        summary_message_threshold: int = 10,
        summary_min_new_messages: int = 4,
    ):
        self.store = store or MemoryStore()
        self.llm_client = llm_client
        self.recent_message_limit = recent_message_limit
        self.summary_message_threshold = summary_message_threshold
        self.summary_min_new_messages = summary_min_new_messages

    def ask(
        self,
        question: str,
        answer_fn: Callable[..., dict[str, Any]],
        paper_id: str | None = None,
        top_k: int = 5,
        conversation_id: str | None = None,
        **answer_kwargs: Any,
    ) -> dict[str, Any]:
        conversation_id = self._ensure_qa_conversation(
            question=question,
            paper_id=paper_id,
            conversation_id=conversation_id,
        )
        conversation = self.store.get_conversation(conversation_id) or {}
        conversation_metadata = parse_metadata(conversation.get("metadata"))
        summary = str(conversation_metadata.get("summary") or "")
        previous_rewritten = str(
            conversation_metadata.get("last_rewritten_question") or ""
        )
        recent_messages = self.store.get_messages(
            conversation_id, limit=self.recent_message_limit
        )
        recent_turns = self._format_turns(recent_messages)

        rewritten_question, rewrite_failed = self._rewrite_question(
            question=question,
            summary=summary,
            recent_turns=recent_turns,
            paper_id=paper_id,
            previous_rewritten_question=previous_rewritten,
        )

        self.store.add_message(
            conversation_id,
            "user",
            question,
            metadata=self._json_metadata(
                {
                    "kind": "qa_user",
                    "paper_id": paper_id,
                    "top_k": top_k,
                }
            ),
        )

        try:
            result = answer_fn(
                question=rewritten_question,
                paper_id=paper_id,
                top_k=top_k,
                conversation_summary=summary,
                recent_turns=recent_turns,
                original_question=question,
                **answer_kwargs,
            )
        except Exception as exc:
            self.store.add_message(
                conversation_id,
                "assistant",
                str(exc),
                metadata=self._json_metadata(
                    {
                        "kind": "qa_assistant",
                        "status": "error",
                        "paper_id": paper_id,
                        "top_k": top_k,
                        "rewritten_question": rewritten_question,
                        "sources": [],
                        "rewrite_failed": rewrite_failed,
                        "error": str(exc),
                    }
                ),
            )
            raise

        sources = result.get("sources", [])
        self.store.add_message(
            conversation_id,
            "assistant",
            str(result.get("answer", "")),
            metadata=self._json_metadata(
                {
                    "kind": "qa_assistant",
                    "status": "done",
                    "paper_id": paper_id,
                    "top_k": top_k,
                    "rewritten_question": rewritten_question,
                    "sources": sources,
                    "retrieval_time": result.get("retrieval_time"),
                    "llm_time": result.get("llm_time"),
                    "rewrite_failed": rewrite_failed,
                }
            ),
        )

        summary_update = self._maybe_update_summary(
            conversation_id, rewritten_question, sources
        )
        metadata_update: dict[str, Any] = {
            "last_rewritten_question": rewritten_question,
        }
        if paper_id is not None:
            metadata_update["default_paper_id"] = paper_id
        if summary_update:
            metadata_update.update(summary_update)
        self.store.update_conversation_metadata(
            conversation_id,
            metadata_update,
        )

        response = dict(result)
        response.update(
            {
                "question": question,
                "conversation_id": conversation_id,
                "rewritten_question": rewritten_question,
                "rewrite_failed": rewrite_failed,
            }
        )
        return response

    def _ensure_qa_conversation(
        self,
        question: str,
        paper_id: str | None,
        conversation_id: str | None,
    ) -> str:
        if conversation_id is None:
            return self.store.create_conversation(
                title=self._title_from_question(question),
                metadata=self._json_metadata(
                    {
                        "kind": "qa",
                        "default_paper_id": paper_id,
                        "summary": "",
                        "summary_message_count": 0,
                    }
                ),
            )

        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        metadata = parse_metadata(conversation.get("metadata"))
        if metadata.get("kind") != "qa":
            raise HTTPException(
                status_code=400,
                detail="Conversation is not a QA conversation",
            )
        return conversation_id

    def _rewrite_question(
        self,
        question: str,
        summary: str,
        recent_turns: str,
        paper_id: str | None = None,
        previous_rewritten_question: str = "",
    ) -> tuple[str, bool]:
        if self.llm_client is None:
            return question, False

        prompt = build_query_rewrite_prompt(
            question,
            conversation_summary=summary,
            recent_turns=recent_turns,
            paper_id=paper_id,
            previous_rewritten_question=previous_rewritten_question,
        )
        try:
            rewritten = str(self.llm_client.generate_text(prompt) or "").strip()
        except Exception:
            return question, True
        return (rewritten or question), False

    def _maybe_update_summary(
        self,
        conversation_id: str,
        rewritten_question: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Compute summary metadata fields to merge, or None if no update."""
        if self.llm_client is None:
            return None

        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            return None

        metadata = parse_metadata(conversation.get("metadata"))
        summary_message_count = self._int_metadata(
            metadata.get("summary_message_count"), default=0
        )
        messages = self.store.get_messages(conversation_id, limit=10000)
        message_count = len(messages)
        new_message_count = message_count - summary_message_count
        if message_count < self.summary_message_threshold:
            return None
        if new_message_count < self.summary_min_new_messages:
            return None

        new_messages = messages[summary_message_count:]
        turns_for_summary = self._format_turns(new_messages[-self.recent_message_limit :])
        source_notes = self._source_notes(sources)
        prompt = build_summary_update_prompt(
            previous_summary=str(metadata.get("summary") or ""),
            recent_turns=turns_for_summary,
            rewritten_question=rewritten_question,
            source_notes=source_notes,
        )
        try:
            updated_summary = str(self.llm_client.generate_text(prompt) or "").strip()
        except Exception:
            return None
        if not updated_summary:
            return None

        return {
            "summary": updated_summary,
            "summary_message_count": message_count,
            "summary_updated_at": time.time(),
        }

    def _format_turns(self, messages: list[dict[str, Any]]) -> str:
        lines = []
        for message in messages:
            role = str(message.get("role") or "").strip() or "unknown"
            content = " ".join(str(message.get("content") or "").split())
            metadata = parse_metadata(message.get("metadata"))
            rewritten = metadata.get("rewritten_question")
            if rewritten:
                lines.append(f"{role}: {content} (rewritten: {rewritten})")
            else:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _source_notes(sources: list[dict[str, Any]]) -> str:
        notes = []
        for source in sources[:5]:
            paper = source.get("paper_id") or "unknown"
            section = source.get("section_path") or source.get("section") or "unknown"
            page = source.get("page_range") or source.get("page_number") or "?"
            notes.append(f"{paper} {section} p.{page}")
        return "\n".join(notes)

    @staticmethod
    def _json_metadata(metadata: dict[str, Any]) -> str:
        return json.dumps(metadata, ensure_ascii=False, default=str)

    @staticmethod
    def _int_metadata(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _title_from_question(question: str) -> str:
        title = " ".join(str(question or "").split())
        return title[:80] if title else "QA conversation"
