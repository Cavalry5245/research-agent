from __future__ import annotations

import logging

from app.prompts.hyde_prompt import build_hyde_prompt

logger = logging.getLogger(__name__)


class HyDE:
    def __init__(self, llm_client, embedding_client, vector_store):
        self._llm = llm_client
        self._embedding = embedding_client
        self._vector_store = vector_store

    def generate_hypothetical_doc(self, query: str) -> str:
        prompt = build_hyde_prompt(query)
        try:
            return (self._llm.generate_text(prompt) or "").strip()
        except Exception as exc:
            logger.warning("HyDE generation failed, fallback to query: %s", exc)
            return query

    def search(
        self, query: str, top_k: int = 5, paper_id: str | None = None
    ) -> list[dict]:
        hypo = self.generate_hypothetical_doc(query) or query
        embedding = self._embedding.embed_query(hypo)
        return self._vector_store.query(embedding, top_k=top_k, paper_id=paper_id)
