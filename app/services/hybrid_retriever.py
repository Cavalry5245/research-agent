from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _min_max_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span <= 0:
        return [0.0 for _ in values]
    return [(v - lo) / span for v in values]


class HybridRetriever:
    def __init__(
        self,
        vector_store,
        embedding_client,
        bm25_retriever,
        alpha: float = 0.5,
        recall_top_k: int = 20,
    ):
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        self._vector_store = vector_store
        self._embedding_client = embedding_client
        self._bm25 = bm25_retriever
        self.alpha = alpha
        self.recall_top_k = recall_top_k

    def search(
        self, query: str, top_k: int = 5, paper_id: str | None = None
    ) -> list[dict]:
        query_emb = self._embedding_client.embed_query(query)
        dense_results = self._vector_store.query(
            query_emb, top_k=self.recall_top_k, paper_id=paper_id
        )
        sparse_results = self._bm25.search(
            query, top_k=self.recall_top_k, paper_id=paper_id
        )

        if not dense_results and not sparse_results:
            return []

        dense_norm = dict(
            zip(
                [r["chunk_id"] for r in dense_results],
                _min_max_normalize([r["score"] for r in dense_results]),
            )
        )
        sparse_norm = dict(
            zip(
                [r["chunk_id"] for r in sparse_results],
                _min_max_normalize([r["score"] for r in sparse_results]),
            )
        )

        merged: dict[str, dict] = {}
        for r in dense_results:
            merged[r["chunk_id"]] = dict(r)
        for r in sparse_results:
            if r["chunk_id"] not in merged:
                merged[r["chunk_id"]] = dict(r)

        for chunk_id, item in merged.items():
            d = dense_norm.get(chunk_id, 0.0)
            s = sparse_norm.get(chunk_id, 0.0)
            item["dense_score"] = d
            item["sparse_score"] = s
            item["score"] = self.alpha * d + (1 - self.alpha) * s

        ranked = sorted(
            merged.values(), key=lambda x: (-x["score"], x.get("chunk_id", ""))
        )
        return ranked[:top_k]
