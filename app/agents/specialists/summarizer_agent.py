"""Summarizer Agent — responsible for note generation and paper summarization."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.specialists import AgentResult, BaseSpecialist

logger = logging.getLogger(__name__)


class SummarizerAgent(BaseSpecialist):
    name = "summarizer"
    role = "摘要专家"
    goal = "生成论文的结构化笔记和摘要，导出 Markdown 文件"
    capabilities = ["summarize", "note", "export"]

    def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        paper_id = context.get("paper_id")
        action = context.get("action", "note")

        if not paper_id:
            return AgentResult(
                success=False, output="", agent_id=self.name, error="需要提供 paper_id"
            )

        if action == "export":
            return self._export_markdown(paper_id)
        return self._generate_note(paper_id)

    def _generate_note(self, paper_id: str) -> AgentResult:
        from app.config import settings
        from app.services.llm_client import LLMClient
        from app.services.note_generator import generate_note
        from app.services.pdf_parser import load_parsed_result

        try:
            parsed = load_parsed_result(paper_id, settings.metadata_dir)
            if not parsed:
                return AgentResult(
                    success=False,
                    output="",
                    agent_id=self.name,
                    error=f"未找到论文: {paper_id}",
                )

            llm = LLMClient()
            note = generate_note(parsed, llm)
            return AgentResult(
                success=True,
                output=f"笔记生成完成，共 {len(note)} 字符",
                data={
                    "paper_id": paper_id,
                    "note_length": len(note),
                    "note_preview": note[:300],
                },
                agent_id=self.name,
            )
        except Exception as e:
            logger.exception("SummarizerAgent note generation failed")
            return AgentResult(
                success=False, output="", agent_id=self.name, error=str(e)
            )

    def _export_markdown(self, paper_id: str) -> AgentResult:
        from app.config import settings
        from app.services.llm_client import LLMClient
        from app.services.markdown_exporter import save_markdown
        from app.services.note_generator import generate_note
        from app.services.pdf_parser import load_parsed_result

        try:
            parsed = load_parsed_result(paper_id, settings.metadata_dir)
            if not parsed:
                return AgentResult(
                    success=False,
                    output="",
                    agent_id=self.name,
                    error=f"未找到论文: {paper_id}",
                )

            llm = LLMClient()
            note = generate_note(parsed, llm)
            path = save_markdown(note, paper_id, settings.note_dir)
            return AgentResult(
                success=True,
                output=f"Markdown 导出完成: {path}",
                data={"paper_id": paper_id, "path": str(path), "length": len(note)},
                agent_id=self.name,
            )
        except Exception as e:
            logger.exception("SummarizerAgent export failed")
            return AgentResult(
                success=False, output="", agent_id=self.name, error=str(e)
            )
