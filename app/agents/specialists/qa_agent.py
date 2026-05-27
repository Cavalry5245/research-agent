"""QA Agent — responsible for RAG-based question answering with rerank and query rewrite."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.specialists import AgentResult, BaseSpecialist

logger = logging.getLogger(__name__)


class QAAgent(BaseSpecialist):
    name = "qa"
    role = "问答专家"
    goal = "基于论文内容回答用户问题，使用 RAG 检索 + rerank + query rewrite"
    capabilities = ["qa", "question", "search"]

    def __init__(self, enable_rerank: bool = True, enable_query_rewrite: bool = False):
        self._enable_rerank = enable_rerank
        self._enable_query_rewrite = enable_query_rewrite

    def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        question = context.get("question", task)
        paper_id = context.get("paper_id")
        top_k = context.get("top_k", 5)

        return self._answer_question(question, paper_id=paper_id, top_k=top_k)

    def _answer_question(
        self, question: str, paper_id: str | None = None, top_k: int = 5
    ) -> AgentResult:
        from app.services.embedding_client import EmbeddingClient
        from app.services.llm_client import LLMClient
        from app.services.paper_qa import answer_question
        from app.services.vector_store import VectorStore

        try:
            vs = VectorStore()
            ec = EmbeddingClient()
            llm = LLMClient()

            kwargs: dict[str, Any] = {}
            if self._enable_rerank:
                from app.services.reranker import CrossEncoderReranker

                kwargs["reranker"] = CrossEncoderReranker()
                kwargs["recall_top_k"] = 20

            if self._enable_query_rewrite:
                from app.services.query_rewriter import QueryRewriter

                rewriter = QueryRewriter(llm)
                rewritten = rewriter.rewrite(question)
                if rewritten:
                    question = rewritten

            result = answer_question(
                question=question,
                vector_store=vs,
                embedding_client=ec,
                llm_client=llm,
                paper_id=paper_id,
                top_k=top_k,
                **kwargs,
            )

            sources = result.get("sources", [])
            return AgentResult(
                success=True,
                output=result.get("answer", ""),
                data={
                    "question": question,
                    "answer": result.get("answer", ""),
                    "sources": sources,
                    "source_count": len(sources),
                },
                agent_id=self.name,
            )
        except Exception as e:
            logger.exception("QAAgent failed")
            return AgentResult(
                success=False, output="", agent_id=self.name, error=str(e)
            )
