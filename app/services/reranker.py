import re
from collections import Counter
from typing import Protocol


class Reranker(Protocol):
    def rerank(self, question: str, results: list[dict], top_k: int | None = None) -> list[dict]:
        """Return retrieval results reordered by relevance to the question."""


class IdentityReranker:
    def rerank(self, question: str, results: list[dict], top_k: int | None = None) -> list[dict]:
        del question
        reranked = []
        for item in results:
            copied = dict(item)
            copied.setdefault("rerank_score", copied.get("score", 0.0))
            reranked.append(copied)
        if top_k is None:
            return reranked
        return reranked[:top_k]



def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9_]+", text.lower()) if token]



def _token_overlap_score(question: str, content: str) -> float:
    question_tokens = _tokenize(question)
    content_tokens = _tokenize(content)
    if not question_tokens or not content_tokens:
        return 0.0

    question_counts = Counter(question_tokens)
    content_counts = Counter(content_tokens)
    overlap = sum(min(question_counts[token], content_counts[token]) for token in question_counts)
    return overlap / len(question_tokens)


class HybridReranker:
    def __init__(self, alpha: float = 0.7):
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        self.alpha = alpha

    def rerank(self, question: str, results: list[dict], top_k: int | None = None) -> list[dict]:
        reranked = []
        for item in results:
            copied = dict(item)
            dense_score = float(copied.get("score", 0.0))
            sparse_score = _token_overlap_score(question=question, content=copied.get("content", ""))
            copied["dense_score"] = dense_score
            copied["sparse_score"] = sparse_score
            copied["rerank_score"] = self.alpha * dense_score + (1 - self.alpha) * sparse_score
            reranked.append(copied)

        reranked.sort(key=lambda item: (-item["rerank_score"], -item.get("score", 0.0), item.get("chunk_id", "")))
        if top_k is None:
            return reranked
        return reranked[:top_k]
