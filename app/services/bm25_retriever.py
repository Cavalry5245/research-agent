from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class RetrieverProtocol(Protocol):
    def search(
        self, query: str, top_k: int, paper_id: str | None = None
    ) -> list[dict]: ...


def tokenize_zh(text: str) -> list[str]:
    import jieba

    return [tok for tok in jieba.lcut(text or "") if tok.strip()]


class BM25Retriever:
    def __init__(self, vector_store, tokenize=None):
        self._vector_store = vector_store
        self._tokenize = tokenize or tokenize_zh
        self._corpus_chunks: list[dict] = []
        self._bm25 = None
        self._built = False

    def _build_index(self, paper_id: str | None = None) -> None:
        from rank_bm25 import BM25Okapi

        chunks = self._vector_store.list_chunks(paper_id=paper_id)
        if not chunks:
            self._corpus_chunks = []
            self._bm25 = None
            self._built = True
            return

        self._corpus_chunks = chunks
        tokenized = [self._tokenize(c.get("content", "")) for c in chunks]
        self._bm25 = BM25Okapi(tokenized)
        self._built = True

    def invalidate(self) -> None:
        self._built = False

    def search(
        self, query: str, top_k: int = 5, paper_id: str | None = None
    ) -> list[dict]:
        self._build_index(paper_id=paper_id)
        if not self._bm25 or not self._corpus_chunks:
            return []

        scores = self._bm25.get_scores(self._tokenize(query))
        ranked_idx = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]

        results: list[dict] = []
        for i in ranked_idx:
            chunk = self._corpus_chunks[i]
            results.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "content": chunk.get("content", ""),
                    "paper_id": chunk.get("paper_id"),
                    "title": chunk.get("title"),
                    "section": chunk.get("section"),
                    "page_number": chunk.get("page_number"),
                    "chunk_start": chunk.get("chunk_start"),
                    "chunk_end": chunk.get("chunk_end"),
                    "score": float(scores[i]),
                }
            )
        return results
