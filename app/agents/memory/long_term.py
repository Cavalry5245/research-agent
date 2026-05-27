"""Long-term memory — user preferences, reading history, and frequent questions."""

from __future__ import annotations

import json
from collections import Counter

from app.services.memory_store import MemoryStore


class LongTermMemory:
    """Persistent storage for user preferences, paper reading history, and question patterns."""

    def __init__(self, store: MemoryStore):
        self._store = store

    # ── User Preferences ─────────────────────────────────────────────────

    def set_preference(self, key: str, value: str) -> None:
        self._store.set_preference(key, value)

    def get_preference(self, key: str) -> str | None:
        return self._store.get_preference(key)

    def get_all_preferences(self) -> dict[str, str]:
        return self._store.list_preferences()

    # ── Reading History ──────────────────────────────────────────────────

    def record_reading(
        self, paper_id: str, action: str = "view", metadata: dict | None = None
    ) -> str:
        return self._store.add_reading_event(
            paper_id=paper_id,
            action=action,
            metadata=json.dumps(metadata or {}, ensure_ascii=False),
        )

    def get_reading_history(
        self, limit: int = 50, paper_id: str | None = None
    ) -> list[dict]:
        return self._store.get_reading_history(limit=limit, paper_id=paper_id)

    def get_recently_read_papers(self, limit: int = 10) -> list[str]:
        history = self._store.get_reading_history(limit=limit * 3)
        seen: list[str] = []
        for event in history:
            if event["paper_id"] not in seen:
                seen.append(event["paper_id"])
            if len(seen) >= limit:
                break
        return seen

    # ── Frequent Questions ───────────────────────────────────────────────

    def record_question(self, question: str, paper_id: str | None = None) -> str:
        metadata = {"question": question}
        if paper_id:
            metadata["paper_id"] = paper_id
        return self._store.add_reading_event(
            paper_id=paper_id or "__global__",
            action="question",
            metadata=json.dumps(metadata, ensure_ascii=False),
        )

    def get_frequent_questions(self, top_k: int = 5) -> list[tuple[str, int]]:
        history = self._store.get_reading_history(limit=500)
        questions: list[str] = []
        for event in history:
            if event["action"] == "question":
                meta = (
                    json.loads(event["metadata"])
                    if isinstance(event["metadata"], str)
                    else event["metadata"]
                )
                q = meta.get("question", "")
                if q:
                    questions.append(q)
        counter = Counter(questions)
        return counter.most_common(top_k)
