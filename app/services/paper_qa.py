import logging
import time
from typing import Protocol

from app.prompts.qa_prompt import build_contextual_qa_prompt, build_qa_prompt
from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient
from app.services.parent_doc_store import ParentDocumentStore
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

CLOSED_CLIENT_MARKERS = (
    "client has been closed",
    "client is closed",
    "cannot send a request, as the client has been closed",
)


class RerankerProtocol(Protocol):
    def rerank(
        self, question: str, results: list[dict], top_k: int | None = None
    ) -> list[dict]: ...


class RetrieverProtocol(Protocol):
    def search(
        self, query: str, top_k: int, paper_id: str | None = None
    ) -> list[dict]: ...


def _build_context(results: list[dict]) -> str:
    """
    构建 QA 上下文。

    优先使用父文档内容（避免重复），向后兼容无父文档的旧数据。
    """
    seen_parents = set()
    parts = []

    for r in results:
        parent_doc = r.get('parent_document')

        if parent_doc:
            # 有父文档：使用完整父文档内容，避免重复
            if parent_doc.parent_id not in seen_parents:
                citation_label = (
                    f"[{parent_doc.paper_id} "
                    f"p.{parent_doc.page_range or '?'} "
                    f"{parent_doc.section_path or 'Unknown'}]"
                )
                parts.append(f"{citation_label}\n{parent_doc.content}")
                seen_parents.add(parent_doc.parent_id)
        else:
            # 向后兼容：没有父文档时使用子块
            citation_label = (
                f"[{r['paper_id']} "
                f"p.{r.get('page_number', '?')} "
                f"{r['section']}]"
            )
            parts.append(f"{citation_label}\n{r['content']}")

    return "\n\n---\n\n".join(parts)


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
    recall_top_k: int | None = None,
    retriever: RetrieverProtocol | None = None,
    parent_store: ParentDocumentStore | None = None,
    conversation_summary: str = "",
    recent_turns: str = "",
    original_question: str | None = None,
) -> dict:
    """
    回答问题，使用父子文档架构。

    新增逻辑：
    1. dense + BM25 hybrid search 子块
    2. optional rerank 子块
    3. 按 parent_id 分组
    4. 从 ParentDocumentStore 加载父文档
    5. 使用父文档构建 prompt context
    6. 生成答案
    """
    logger.info(
        "QA: question='%s', paper_id=%s, top_k=%d", question[:80], paper_id, top_k
    )

    if llm_client_factory is None:
        llm_client_factory = LLMClient

    effective_recall_top_k = recall_top_k if recall_top_k is not None else top_k

    retrieval_start = time.perf_counter()
    if retriever is not None:
        results = retriever.search(
            query=question, top_k=effective_recall_top_k, paper_id=paper_id
        )
    else:
        query_emb = embedding_client.embed_query(question)
        results = vector_store.query(
            query_emb, top_k=effective_recall_top_k, paper_id=paper_id
        )
    retrieval_seconds = time.perf_counter() - retrieval_start

    if not results:
        _emit_qa_event(
            question=question,
            paper_id=paper_id,
            top_k=top_k,
            answer="",
            retrieval_time=retrieval_seconds,
            llm_time=0.0,
            sources=[],
        )
        return {
            "question": question,
            "answer": "当前知识库中没有检索到相关内容。请先上传并索引论文。",
            "sources": [],
        }

    results = _apply_reranker(
        question=question, results=results, reranker=reranker, top_k=top_k
    )

    # 父文档回填逻辑
    if parent_store is None:
        parent_store = ParentDocumentStore()

    # 提取 parent_ids（去重）
    parent_ids = list(set([
        chunk.get('parent_id')
        for chunk in results
        if chunk.get('parent_id')
    ]))

    # 如果有 parent_id，加载父文档
    if parent_ids:
        logger.info("Loading %d parent documents for QA context", len(parent_ids))
        parents = parent_store.get_parents(parent_ids)
        # 构建 parent_id -> ParentDocument 映射
        parent_map = {p.parent_id: p for p in parents}

        # 为每个子块关联父文档
        for chunk in results:
            pid = chunk.get('parent_id')
            if pid and pid in parent_map:
                chunk['parent_document'] = parent_map[pid]

        logger.info(
            "Successfully loaded %d/%d parent documents",
            len(parent_map),
            len(parent_ids)
        )
    else:
        # 向后兼容：没有 parent_id 的旧数据
        logger.debug("No parent_ids found in results, using child chunks directly")

    context = _build_context(results)
    if conversation_summary or recent_turns or original_question:
        prompt = build_contextual_qa_prompt(
            question=original_question or question,
            rewritten_question=question,
            context=context,
            conversation_summary=conversation_summary,
            recent_turns=recent_turns,
        )
    else:
        prompt = build_qa_prompt(question, context)

    llm_start = time.perf_counter()
    try:
        answer = llm_client.generate_text(prompt)
    except RuntimeError as e:
        if _is_closed_client_error(e):
            logger.warning(
                "LLM client was closed during QA, recreating client and retrying once"
            )
            answer = llm_client_factory().generate_text(prompt)
        else:
            raise
    llm_seconds = time.perf_counter() - llm_start

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
            "parent_id": r.get("parent_id"),
            "section_path": r.get("section_path"),
            "page_range": (
                r["parent_document"].page_range
                if r.get("parent_document")
                else r.get("page_range")
            ),
            "element_type": r.get("element_type"),
        }
        for r in results
    ]

    logger.info(
        "qa_completed",
        extra={
            "ra_paper_id": paper_id,
            "ra_top_k": top_k,
            "ra_sources_count": len(sources),
            "ra_retrieval_ms": round(retrieval_seconds * 1000, 2),
            "ra_llm_ms": round(llm_seconds * 1000, 2),
        },
    )
    _emit_qa_event(
        question=question,
        paper_id=paper_id,
        top_k=top_k,
        answer=answer,
        retrieval_time=retrieval_seconds,
        llm_time=llm_seconds,
        sources=sources,
    )

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "retrieval_time": retrieval_seconds,
        "llm_time": llm_seconds,
    }


def _emit_qa_event(
    question: str,
    paper_id: str | None,
    top_k: int,
    answer: str,
    retrieval_time: float,
    llm_time: float,
    sources: list[dict],
) -> None:
    """Best-effort analytics emit; never break the QA path on failure."""
    try:
        from app.analytics import get_collector

        get_collector().log_qa_request(
            paper_id=paper_id,
            question=question,
            answer=answer,
            retrieval_time=retrieval_time,
            llm_time=llm_time,
            sources_count=len(sources),
            top_k=top_k,
        )
    except Exception as exc:
        logger.debug("Analytics emit skipped: %s", exc)
