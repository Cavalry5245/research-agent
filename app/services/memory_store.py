"""SQLite-backed memory store for conversations, messages, preferences, and reading history."""

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("app/storage") / "memory.db"


def parse_metadata(raw_metadata: Any) -> dict[str, Any]:
    """Decode a conversation/message metadata blob (JSON string or dict)."""
    if isinstance(raw_metadata, dict):
        return raw_metadata
    try:
        decoded = json.loads(raw_metadata or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS reading_history (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_reading_paper ON reading_history(paper_id);
CREATE INDEX IF NOT EXISTS idx_reading_time ON reading_history(created_at DESC);

CREATE TABLE IF NOT EXISTS semantic_facts (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS agent_traces (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    agent_id TEXT NOT NULL,
    action TEXT NOT NULL,
    input_data TEXT NOT NULL DEFAULT '{}',
    output_data TEXT NOT NULL DEFAULT '{}',
    duration_ms REAL,
    created_at REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_traces_conv ON agent_traces(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_traces_agent ON agent_traces(agent_id, created_at);
"""


class MemoryStore:
    """Thread-safe SQLite memory store."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or DEFAULT_DB_PATH)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self):
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ── Conversations ────────────────────────────────────────────────────

    def create_conversation(self, title: str = "", metadata: str = "{}") -> str:
        conv_id = str(uuid.uuid4())
        now = time.time()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?)",
            (conv_id, title, now, now, metadata),
        )
        conn.commit()
        return conv_id

    def list_conversations(self, limit: int = 50, offset: int = 0) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_conversations(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()
        return int(row[0])

    def count_conversations_by_kind(self, kind: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE json_extract(metadata, '$.kind') = ?",
            (kind,),
        ).fetchone()
        return int(row[0])

    def list_conversations_by_kind(
        self, kind: str, limit: int | None = None, offset: int = 0
    ) -> list[dict]:
        conn = self._get_conn()
        sql = (
            "SELECT * FROM conversations WHERE json_extract(metadata, '$.kind') = ? "
            "ORDER BY updated_at DESC"
        )
        params: list[Any] = [kind]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_conversation(self, conv_id: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_conversation_metadata(
        self, conversation_id: str, metadata: dict[str, Any] | str
    ) -> bool:
        conv = self.get_conversation(conversation_id)
        if not conv:
            return False
        merged = parse_metadata(conv.get("metadata"))
        merged.update(parse_metadata(metadata))
        now = time.time()
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE conversations SET metadata = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged), now, conversation_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def update_conversation_title(
        self, conversation_id: str, title: str | None
    ) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title or "", time.time(), conversation_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_conversation(self, conv_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ── Messages ─────────────────────────────────────────────────────────

    def add_message(
        self, conversation_id: str, role: str, content: str, metadata: str = "{}"
    ) -> str:
        msg_id = str(uuid.uuid4())
        now = time.time()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, now, metadata),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        conn.commit()
        return msg_id

    def get_messages(
        self, conversation_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
            (conversation_id, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_messages(self, conversation_id: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return row["cnt"]

    # ── User Preferences ─────────────────────────────────────────────────

    def set_preference(self, key: str, value: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        conn.commit()

    def get_preference(self, key: str) -> str | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM user_preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def list_preferences(self) -> dict[str, str]:
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ── Reading History ──────────────────────────────────────────────────

    def add_reading_event(
        self, paper_id: str, action: str, metadata: str = "{}"
    ) -> str:
        event_id = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO reading_history (id, paper_id, action, created_at, metadata) VALUES (?, ?, ?, ?, ?)",
            (event_id, paper_id, action, time.time(), metadata),
        )
        conn.commit()
        return event_id

    def get_reading_history(
        self, limit: int = 50, paper_id: str | None = None
    ) -> list[dict]:
        conn = self._get_conn()
        if paper_id:
            rows = conn.execute(
                "SELECT * FROM reading_history WHERE paper_id = ? ORDER BY created_at DESC LIMIT ?",
                (paper_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reading_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Semantic Facts ───────────────────────────────────────────────────

    def add_fact(self, content: str, metadata: str = "{}") -> str:
        fact_id = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO semantic_facts (id, content, created_at, metadata) VALUES (?, ?, ?, ?)",
            (fact_id, content, time.time(), metadata),
        )
        conn.commit()
        return fact_id

    def list_facts(self, limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM semantic_facts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_fact(self, fact_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM semantic_facts WHERE id = ?", (fact_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ── Agent Traces ─────────────────────────────────────────────────────

    def add_trace(
        self,
        agent_id: str,
        action: str,
        input_data: str = "{}",
        output_data: str = "{}",
        duration_ms: float | None = None,
        conversation_id: str | None = None,
        metadata: str = "{}",
    ) -> str:
        trace_id = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO agent_traces (id, conversation_id, agent_id, action, input_data, output_data, duration_ms, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                conversation_id,
                agent_id,
                action,
                input_data,
                output_data,
                duration_ms,
                time.time(),
                metadata,
            ),
        )
        conn.commit()
        return trace_id

    def get_traces(
        self,
        conversation_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        conn = self._get_conn()
        conditions = []
        params: list[Any] = []
        if conversation_id:
            conditions.append("conversation_id = ?")
            params.append(conversation_id)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM agent_traces {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
