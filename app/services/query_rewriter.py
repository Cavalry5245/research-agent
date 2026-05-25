from __future__ import annotations

import logging

from app.prompts.query_rewrite_prompt import build_query_rewrite_prompt

logger = logging.getLogger(__name__)


class QueryRewriter:
    def __init__(self, llm_client):
        self._llm = llm_client

    def rewrite(self, query: str) -> str:
        if not query or not query.strip():
            return query
        try:
            prompt = build_query_rewrite_prompt(query)
            rewritten = self._llm.generate_text(prompt)
            rewritten = (rewritten or "").strip().split("\n")[0]
            return rewritten or query
        except Exception as exc:
            logger.warning("Query rewrite failed, fallback to original: %s", exc)
            return query
