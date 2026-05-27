"""Comparator Agent — responsible for multi-paper comparison analysis."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.specialists import AgentResult, BaseSpecialist

logger = logging.getLogger(__name__)


class ComparatorAgent(BaseSpecialist):
    name = "comparator"
    role = "对比分析专家"
    goal = "对比多篇论文的异同，生成结构化对比报告"
    capabilities = ["compare", "contrast", "diff"]

    def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        paper_ids = context.get("paper_ids", [])

        if len(paper_ids) < 2:
            return AgentResult(
                success=False,
                output="",
                agent_id=self.name,
                error="至少需要 2 篇论文进行对比（提供 paper_ids 列表）",
            )

        return self._compare_papers(paper_ids)

    def _compare_papers(self, paper_ids: list[str]) -> AgentResult:
        from app.config import settings
        from app.services.llm_client import LLMClient
        from app.services.paper_compare import compare_papers
        from app.services.pdf_parser import load_parsed_result

        try:
            papers = []
            for pid in paper_ids:
                parsed = load_parsed_result(pid, settings.metadata_dir)
                if not parsed:
                    return AgentResult(
                        success=False,
                        output="",
                        agent_id=self.name,
                        error=f"未找到论文: {pid}",
                    )
                papers.append(parsed)

            llm = LLMClient()
            result = compare_papers(papers, llm)

            return AgentResult(
                success=True,
                output=f"对比完成: {len(paper_ids)} 篇论文",
                data={
                    "paper_ids": paper_ids,
                    "comparison": result,
                    "paper_count": len(paper_ids),
                },
                agent_id=self.name,
            )
        except Exception as e:
            logger.exception("ComparatorAgent failed")
            return AgentResult(
                success=False, output="", agent_id=self.name, error=str(e)
            )
