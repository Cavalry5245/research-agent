import logging
from typing import Protocol

from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient
from app.services.vector_store import VectorStore
from app.prompts.qa_prompt import build_qa_prompt

logger = logging.getLogger(__name__)

CLOSED_CLIENT_MARKERS = (
    "client has been closed",
    "client is closed",
    "cannot send a request, as the client has been closed",
)


class RerankerProtocol(Protocol):
    def rerank(self, question: str, results: list[dict], top_k: int | None = None) -> list[dict]:
        ...


def _build_context(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[片段 {i}] "
            f"Paper: {r['paper_id']}, "
            f"Title: {r['title']}, "
            f"Section: {r['section']}\n"
            f"{r['content']}"
        )
    return "\n\n".join(parts)


def _is_closed_client_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in CLOSED_CLIENT_MARKERS)


def _apply_reranker(
    question: str,
    results: list[dict],
    reranker: RerankerProtocol | None,
    top_k: int,
) -> list[dict]:
    if reranker is None:
        return results

    reranked = reranker.rerank(question=question, results=results, top_k=top_k)
    if not reranked:
        raise ValueError("reranker returned empty results")

    reranked_chunk_ids = {item.get("chunk_id") for item in reranked}
    original_chunk_ids = {item.get("chunk_id") for item in results}
    if not reranked_chunk_ids.issubset(original_chunk_ids):
        raise ValueError("reranker returned unknown chunk ids")

    normalized = []
    for item in reranked[:top_k]:
        copied = dict(item)
        copied.setdefault("rerank_score", copied.get("score", 0.0))
        normalized.append(copied)
    return normalized


def answer_question(
    question: str,
    vector_store: VectorStore,
    embedding_client: EmbeddingClient,
    llm_client: LLMClient,
    paper_id: str | None = None,
    top_k: int = 5,
    llm_client_factory=None,
    reranker: RerankerProtocol | None = None,
) -> dict:
    logger.info("QA: question='%s', paper_id=%s, top_k=%d", question[:80], paper_id, top_k)

    if llm_client_factory is None:
        llm_client_factory = LLMClient

    query_emb = embedding_client.embed_query(question)
    results = vector_store.query(query_emb, top_k=top_k, paper_id=paper_id)

    if not results:
        return {
            "question": question,
            "answer": "当前知识库中没有检索到相关内容。请先上传并索引论文。",
            "sources": [],
        }

    results = _apply_reranker(question=question, results=results, reranker=reranker, top_k=top_k)
    context = _build_context(results)
    prompt = build_qa_prompt(question, context)

    try:
        answer = llm_client.generate_text(prompt)
    except RuntimeError as e:
        if _is_closed_client_error(e):
            logger.warning("LLM client was closed during QA, recreating client and retrying once")
            answer = llm_client_factory().generate_text(prompt)
        else:
            raise

    sources = [
        {
            "paper_id": r["paper_id"],
            "title": r["title"],
            "section": r["section"],
            "chunk_id": r["chunk_id"],
            "content": r["content"][:200],
            "score": r.get("rerank_score", r.get("score")),
            "page_number": r.get("page_number"),
            "chunk_start": r.get("chunk_start"),
            "chunk_end": r.get("chunk_end"),
        }
        for r in results
    ]


    return {
        "question": question,
        "answer": answer,
        "sources": sources,
    }
