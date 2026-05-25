"""Semantic memory — vector-based fact storage and recall."""

from __future__ import annotations

import json
import math
from typing import Any

from app.services.memory_store import MemoryStore


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticMemory:
    """Stores facts as embeddings and retrieves by semantic similarity.

    Uses the project's EmbeddingClient for encoding and an in-memory index
    backed by SQLite for persistence.
    """

    def __init__(self, store: MemoryStore, embedding_client: Any = None):
        self._store = store
        self._embedding_client = embedding_client
        self._cache: dict[str, list[float]] = {}

    def _get_embedding_client(self) -> Any:
        if self._embedding_client is None:
            from app.services.embedding_client import EmbeddingClient
            self._embedding_client = EmbeddingClient()
        return self._embedding_client

    def store_fact(self, content: str, metadata: dict | None = None) -> str:
        ec = self._get_embedding_client()
        embedding = ec.embed_query(content)
        meta = metadata or {}
        meta["embedding"] = embedding
        fact_id = self._store.add_fact(content, json.dumps(meta, ensure_ascii=False))
        self._cache[fact_id] = embedding
        return fact_id

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        ec = self._get_embedding_client()
        query_embedding = ec.embed_query(query)

        facts = self._store.list_facts(limit=1000)
        scored: list[tuple[float, dict]] = []
        for fact in facts:
            meta = json.loads(fact["metadata"]) if isinstance(fact["metadata"], str) else fact["metadata"]
            embedding = meta.get("embedding")
            if not embedding:
                continue
            score = _cosine_similarity(query_embedding, embedding)
            scored.append((score, {"id": fact["id"], "content": fact["content"], "score": score}))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def delete_fact(self, fact_id: str) -> bool:
        self._cache.pop(fact_id, None)
        return self._store.delete_fact(fact_id)
