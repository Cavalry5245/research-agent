"""
Reader Agent for Research Pipeline.

Extracts structured information from papers in abstract-only or PDF mode.
"""

import logging
from typing import Any

from app.research_pipeline.schemas import PaperCandidate, PaperCard
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ReaderAgent:
    """
    Reader agent that extracts structured information from papers.

    Supports two extraction modes:
    - abstract_only: When no PDF is available, extracts from title/abstract/metadata
    - pdf: Full PDF extraction (not yet implemented)
    """

    def __init__(self, db_path: str):
        """
        Initialize the reader agent.

        Args:
            db_path: Path to SQLite database for storing paper cards.
        """
        self.db_path = db_path
        self.llm_client = None

        # Try to initialize LLM client
        try:
            self.llm_client = LLMClient()
            logger.info("ReaderAgent initialized with LLM support")
        except (ValueError, Exception) as e:
            logger.warning("ReaderAgent initialized without LLM support: %s", e)
            self.llm_client = None

    def read_paper(
        self,
        candidate: PaperCandidate,
        reading_focus: str | None = None,
    ) -> PaperCard:
        """
        Read a paper and extract structured information.

        Args:
            candidate: Paper candidate to read.
            reading_focus: Optional reading focus to guide extraction.

        Returns:
            PaperCard with extracted information.
        """
        # Determine extraction mode
        if candidate.local_pdf_path is None:
            extraction_mode = "abstract_only"
            return self._read_abstract_only(candidate, reading_focus)
        else:
            # PDF mode not yet implemented
            raise NotImplementedError("PDF extraction mode not yet implemented")

    def _read_abstract_only(
        self,
        candidate: PaperCandidate,
        reading_focus: str | None = None,
    ) -> PaperCard:
        """
        Extract information from title, abstract, and metadata only.

        Args:
            candidate: Paper candidate.
            reading_focus: Optional reading focus.

        Returns:
            PaperCard with extracted information.
        """
        # Build bibliographic metadata
        bibliographic_metadata = {
            "authors": candidate.authors,
            "year": candidate.year,
            "venue": candidate.venue,
            "doi": candidate.doi,
            "source": candidate.source,
            "url": candidate.url,
            "citation_count": candidate.citation_count,
        }

        # Try LLM extraction if available
        if self.llm_client is not None:
            try:
                card = self._extract_with_llm(candidate, reading_focus, bibliographic_metadata)
                return card
            except Exception as e:
                logger.error("LLM extraction failed for %s: %s", candidate.paper_id, e)
                # Fall through to fallback

        # Fallback: generate degraded card without LLM
        return self._generate_fallback_card(candidate, bibliographic_metadata)

    def _extract_with_llm(
        self,
        candidate: PaperCandidate,
        reading_focus: str | None,
        bibliographic_metadata: dict[str, Any],
    ) -> PaperCard:
        """
        Extract structured information using LLM.

        Args:
            candidate: Paper candidate.
            reading_focus: Optional reading focus.
            bibliographic_metadata: Pre-built bibliographic metadata.

        Returns:
            PaperCard with LLM-extracted information.
        """
        # Build prompt
        prompt = self._build_extraction_prompt(candidate, reading_focus)

        # Call LLM
        logger.info("Extracting from abstract for paper_id=%s", candidate.paper_id)
        response = self.llm_client.generate_text(prompt)

        # Parse LLM response
        extracted = self._parse_llm_response(response)

        # Build PaperCard
        card = PaperCard(
            paper_id=candidate.paper_id,
            status="completed",
            extraction_mode="abstract_only",
            title=candidate.title,
            bibliographic_metadata=bibliographic_metadata,
            research_problem=extracted.get("research_problem", ""),
            method=extracted.get("method", ""),
            datasets=extracted.get("datasets", []),
            metrics=extracted.get("metrics", []),
            key_results=extracted.get("key_results", []),
            limitations=extracted.get("limitations", []),
            assumptions=extracted.get("assumptions", []),
            future_work=extracted.get("future_work", []),
            claims=[],
            evidence=[],
            error=None,
        )

        return card

    def _generate_fallback_card(
        self,
        candidate: PaperCandidate,
        bibliographic_metadata: dict[str, Any],
    ) -> PaperCard:
        """
        Generate a degraded card without LLM.

        Args:
            candidate: Paper candidate.
            bibliographic_metadata: Pre-built bibliographic metadata.

        Returns:
            PaperCard with fallback information.
        """
        # Use abstract as research problem if available
        research_problem = ""
        if candidate.abstract:
            # Truncate abstract to reasonable length for research problem field
            research_problem = candidate.abstract[:500]
            if len(candidate.abstract) > 500:
                research_problem += "..."

        # Store full abstract in metadata if available
        if candidate.abstract:
            bibliographic_metadata["abstract"] = candidate.abstract

        card = PaperCard(
            paper_id=candidate.paper_id,
            status="degraded",
            extraction_mode="abstract_only",
            title=candidate.title,
            bibliographic_metadata=bibliographic_metadata,
            research_problem=research_problem,
            method="",
            datasets=[],
            metrics=[],
            key_results=[],
            limitations=[],
            assumptions=[],
            future_work=[],
            claims=[],
            evidence=[],
            error="LLM不可用，仅提取基础元数据",
        )

        logger.info(
            "Generated fallback card for paper_id=%s (status=degraded)",
            candidate.paper_id,
        )

        return card

    def _build_extraction_prompt(
        self,
        candidate: PaperCandidate,
        reading_focus: str | None,
    ) -> str:
        """
        Build LLM prompt for abstract-only extraction.

        Args:
            candidate: Paper candidate.
            reading_focus: Optional reading focus.

        Returns:
            Prompt string.
        """
        focus_section = ""
        if reading_focus:
            focus_section = f"\n\n**阅读重点:** {reading_focus}\n"

        abstract_text = candidate.abstract or "无摘要"

        prompt = f"""你是一个学术论文分析专家。请从以下论文的标题和摘要中提取结构化信息。

**论文标题:** {candidate.title}

**作者:** {', '.join(candidate.authors) if candidate.authors else '未知'}

**年份:** {candidate.year or '未知'}

**摘要:**
{abstract_text}
{focus_section}
请提取以下信息（如果摘要中未明确说明，请标注"原文未明确说明"）：

1. **研究问题:** 论文要解决什么问题或研究什么主题？
2. **方法:** 使用了什么方法或技术？
3. **数据集:** 使用了哪些数据集？（如果提到，列出数据集名称）
4. **指标:** 使用了哪些评估指标？（如果提到，列出指标名称）
5. **关键结果:** 主要发现或结果是什么？
6. **局限性:** 论文提到的局限性或限制条件？
7. **假设:** 研究基于的假设或前提条件？
8. **未来工作:** 论文提到的未来研究方向？

请用简洁的中文回答，每个字段独立一行。如果某个字段在摘要中没有信息，写"原文未明确说明"。
"""

        return prompt

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """
        Parse LLM response into structured fields.

        Args:
            response: LLM response text.

        Returns:
            Dictionary with extracted fields.
        """
        result: dict[str, Any] = {
            "research_problem": "",
            "method": "",
            "datasets": [],
            "metrics": [],
            "key_results": [],
            "limitations": [],
            "assumptions": [],
            "future_work": [],
        }

        lines = response.strip().split("\n")

        current_field = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts a new field
            if "研究问题:" in line or "研究问题：" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "research_problem"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            elif "方法:" in line or "方法：" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "method"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            elif "数据集:" in line or "数据集：" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "datasets"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            elif "指标:" in line or "指标：" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "metrics"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            elif "关键结果:" in line or "关键结果：" in line or "主要发现:" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "key_results"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            elif "局限性:" in line or "局限性：" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "limitations"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            elif "假设:" in line or "假设：" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "assumptions"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            elif "未来工作:" in line or "未来工作：" in line or "未来研究:" in line:
                if current_field and current_content:
                    self._store_parsed_field(result, current_field, current_content)
                current_field = "future_work"
                current_content = [line.split(":", 1)[-1].split("：", 1)[-1].strip()]
            else:
                # Continuation of current field
                if current_field:
                    current_content.append(line)

        # Store last field
        if current_field and current_content:
            self._store_parsed_field(result, current_field, current_content)

        return result

    def _store_parsed_field(
        self,
        result: dict[str, Any],
        field_name: str,
        content: list[str],
    ) -> None:
        """
        Store parsed field content in result dictionary.

        Args:
            result: Result dictionary to update.
            field_name: Field name.
            content: Content lines.
        """
        joined_content = " ".join(content).strip()

        # Skip if content indicates unavailable information
        if "原文未明确说明" in joined_content or not joined_content:
            return

        # Store based on field type
        if field_name in ["research_problem", "method"]:
            result[field_name] = joined_content
        elif field_name in ["datasets", "metrics", "key_results", "limitations", "assumptions", "future_work"]:
            # Split by common delimiters for list fields
            items = []
            for delimiter in ["、", "；", ";", ","]:
                if delimiter in joined_content:
                    items = [item.strip() for item in joined_content.split(delimiter) if item.strip()]
                    break

            if not items:
                # Single item
                items = [joined_content]

            result[field_name] = items
