"""Short-term memory — conversation history with sliding window truncation."""

from __future__ import annotations

from app.services.memory_store import MemoryStore


class ShortTermMemory:
    """Manages conversation-scoped message history with a configurable window size."""

    def __init__(self, store: MemoryStore, max_messages: int = 20):
        self._store = store
        self._max_messages = max_messages

    def create_conversation(self, title: str = "") -> str:
        return self._store.create_conversation(title=title)

    def add_message(self, conversation_id: str, role: str, content: str) -> str:
        msg_id = self._store.add_message(conversation_id, role, content)
        self._truncate(conversation_id)
        return msg_id

    def get_context(self, conversation_id: str) -> list[dict]:
        messages = self._store.get_messages(conversation_id, limit=self._max_messages)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def get_full_history(self, conversation_id: str, limit: int = 100) -> list[dict]:
        return self._store.get_messages(conversation_id, limit=limit)

    def _truncate(self, conversation_id: str) -> None:
        count = self._store.count_messages(conversation_id)
        if count <= self._max_messages:
            return
        overflow = count - self._max_messages
        conn = self._store._get_conn()
        conn.execute(
            """DELETE FROM messages WHERE id IN (
                SELECT id FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            )""",
            (conversation_id, overflow),
        )
        conn.commit()
