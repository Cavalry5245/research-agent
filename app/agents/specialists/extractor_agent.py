"""Extractor Agent — responsible for PDF parsing and structured information extraction."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.specialists import AgentResult, BaseSpecialist

logger = logging.getLogger(__name__)


class ExtractorAgent(BaseSpecialist):
    name = "extractor"
    role = "信息提取专家"
    goal = "从学术论文中解析和提取结构化信息（标题、摘要、章节、方法、数据集等）"
    capabilities = ["upload", "parse", "extract"]

    def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        file_path = context.get("file_path")
        paper_id = context.get("paper_id")

        if file_path:
            return self._parse_pdf(file_path)
        elif paper_id:
            return self._extract_info(paper_id)
        else:
            return AgentResult(
                success=False,
                output="",
                agent_id=self.name,
                error="需要提供 file_path（解析PDF）或 paper_id（提取信息）",
            )

    def _parse_pdf(self, file_path: str) -> AgentResult:
        import os

        from app.config import settings
        from app.services.pdf_parser import (
            generate_paper_id,
            parse_pdf,
            save_parse_result,
        )

        if not os.path.isfile(file_path):
            return AgentResult(
                success=False,
                output="",
                agent_id=self.name,
                error=f"文件不存在: {file_path}",
            )

        try:
            paper_id = generate_paper_id(settings.upload_dir)
            result = parse_pdf(file_path, paper_id)
            save_parse_result(result, settings.metadata_dir)
            return AgentResult(
                success=True,
                output=f"论文解析完成: {result.title}",
                data={
                    "paper_id": paper_id,
                    "title": result.title,
                    "sections": len(result.sections),
                },
                agent_id=self.name,
            )
        except Exception as e:
            logger.exception("ExtractorAgent parse failed")
            return AgentResult(
                success=False, output="", agent_id=self.name, error=str(e)
            )

    def _extract_info(self, paper_id: str) -> AgentResult:
        from app.config import settings
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
            sections = [s.heading for s in parsed.sections] if parsed.sections else []
            return AgentResult(
                success=True,
                output=f"论文 '{parsed.title}' 包含 {len(sections)} 个章节",
                data={
                    "paper_id": paper_id,
                    "title": parsed.title,
                    "abstract": parsed.abstract[:200] if parsed.abstract else "",
                    "sections": sections,
                },
                agent_id=self.name,
            )
        except Exception as e:
            logger.exception("ExtractorAgent extract failed")
            return AgentResult(
                success=False, output="", agent_id=self.name, error=str(e)
            )
