"""
Reader Agent for Research Pipeline.

Extracts structured information from papers in abstract-only or PDF mode.
"""

import logging
from typing import Any

from app.research_pipeline.schemas import PaperCandidate, PaperCard
from app.services.llm_client import LLMClient
from app.services.pdf_parser import parse_pdf

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
            # PDF mode
            return self._read_pdf(candidate, reading_focus)

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

    def _read_pdf(
        self,
        candidate: PaperCandidate,
        reading_focus: str | None = None,
    ) -> PaperCard:
        """
        Extract information from local PDF file.

        Args:
            candidate: Paper candidate with local_pdf_path.
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

        # Try to parse PDF
        try:
            logger.info("Parsing PDF for paper_id=%s from %s", candidate.paper_id, candidate.local_pdf_path)
            parse_result = parse_pdf(candidate.local_pdf_path, candidate.paper_id)
        except Exception as e:
            # PDF parsing failed - return failed/degraded card
            logger.error("PDF parsing failed for %s: %s", candidate.paper_id, e)
            return self._generate_pdf_failed_card(candidate, bibliographic_metadata, str(e))

        # PDF parsed successfully - extract with LLM if available
        if self.llm_client is not None:
            try:
                card = self._extract_from_pdf_with_llm(
                    candidate, parse_result, reading_focus, bibliographic_metadata
                )
                return card
            except Exception as e:
                logger.error("LLM extraction from PDF failed for %s: %s", candidate.paper_id, e)
                # Fall through to fallback

        # Fallback: generate degraded card without LLM but with PDF content
        return self._generate_pdf_fallback_card(candidate, parse_result, bibliographic_metadata)

    def _extract_from_pdf_with_llm(
        self,
        candidate: PaperCandidate,
        parse_result: Any,
        reading_focus: str | None,
        bibliographic_metadata: dict[str, Any],
    ) -> PaperCard:
        """
        Extract structured information from PDF using LLM.

        Args:
            candidate: Paper candidate.
            parse_result: PDF parse result from parse_pdf().
            reading_focus: Optional reading focus.
            bibliographic_metadata: Pre-built bibliographic metadata.

        Returns:
            PaperCard with LLM-extracted information.
        """
        # Build prompt from PDF content
        prompt = self._build_pdf_extraction_prompt(candidate, parse_result, reading_focus)

        # Call LLM
        logger.info("Extracting from PDF for paper_id=%s", candidate.paper_id)
        response = self.llm_client.generate_text(prompt)

        # Parse LLM response
        extracted = self._parse_llm_response(response)

        # Build evidence from PDF sections
        evidence = self._extract_evidence_from_sections(parse_result.sections, candidate.paper_id)

        # Build PaperCard
        card = PaperCard(
            paper_id=candidate.paper_id,
            status="completed",
            extraction_mode="pdf",
            title=parse_result.title or candidate.title,
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
            evidence=evidence,
            error=None,
        )

        return card

    def _generate_pdf_failed_card(
        self,
        candidate: PaperCandidate,
        bibliographic_metadata: dict[str, Any],
        error_message: str,
    ) -> PaperCard:
        """
        Generate a failed card when PDF parsing fails.

        Args:
            candidate: Paper candidate.
            bibliographic_metadata: Pre-built bibliographic metadata.
            error_message: Error message from parsing failure.

        Returns:
            PaperCard with failed status.
        """
        card = PaperCard(
            paper_id=candidate.paper_id,
            status="failed",
            extraction_mode="pdf",
            title=candidate.title,
            bibliographic_metadata=bibliographic_metadata,
            research_problem="",
            method="",
            datasets=[],
            metrics=[],
            key_results=[],
            limitations=[],
            assumptions=[],
            future_work=[],
            claims=[],
            evidence=[],
            error=f"PDF解析失败: {error_message}",
        )

        logger.info(
            "Generated failed card for paper_id=%s (status=failed)",
            candidate.paper_id,
        )

        return card

    def _generate_pdf_fallback_card(
        self,
        candidate: PaperCandidate,
        parse_result: Any,
        bibliographic_metadata: dict[str, Any],
    ) -> PaperCard:
        """
        Generate a degraded card without LLM but with PDF content.

        Args:
            candidate: Paper candidate.
            parse_result: PDF parse result.
            bibliographic_metadata: Pre-built bibliographic metadata.

        Returns:
            PaperCard with fallback information.
        """
        # Use abstract as research problem if available
        research_problem = ""
        if parse_result.abstract:
            research_problem = parse_result.abstract[:500]
            if len(parse_result.abstract) > 500:
                research_problem += "..."

        # Store abstract in metadata
        if parse_result.abstract:
            bibliographic_metadata["abstract"] = parse_result.abstract

        # Build evidence from PDF sections
        evidence = self._extract_evidence_from_sections(parse_result.sections, candidate.paper_id)

        card = PaperCard(
            paper_id=candidate.paper_id,
            status="degraded",
            extraction_mode="pdf",
            title=parse_result.title or candidate.title,
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
            evidence=evidence,
            error="LLM不可用，仅提取PDF基础内容",
        )

        logger.info(
            "Generated PDF fallback card for paper_id=%s (status=degraded)",
            candidate.paper_id,
        )

        return card

    def _build_pdf_extraction_prompt(
        self,
        candidate: PaperCandidate,
        parse_result: Any,
        reading_focus: str | None,
    ) -> str:
        """
        Build LLM prompt for PDF extraction.

        Args:
            candidate: Paper candidate.
            parse_result: PDF parse result.
            reading_focus: Optional reading focus.

        Returns:
            Prompt string.
        """
        focus_section = ""
        if reading_focus:
            focus_section = f"\n\n**阅读重点:** {reading_focus}\n"

        # Build sections text
        sections_text = ""
        for section in parse_result.sections[:10]:  # Limit to first 10 sections
            page_info = f" (p.{section.page_number})" if section.page_number else ""
            sections_text += f"\n### {section.heading}{page_info}\n{section.content[:1000]}\n"

        abstract_text = parse_result.abstract or "无摘要"

        prompt = f"""你是一个学术论文分析专家。请从以下论文的全文中提取结构化信息。

**论文标题:** {parse_result.title or candidate.title}

**作者:** {', '.join(candidate.authors) if candidate.authors else '未知'}

**年份:** {candidate.year or '未知'}

**摘要:**
{abstract_text}

**论文章节内容:**
{sections_text}
{focus_section}
请提取以下信息（如果论文中未明确说明，请标注"原文未明确说明"）：

1. **研究问题:** 论文要解决什么问题或研究什么主题？
2. **方法:** 使用了什么方法或技术？
3. **数据集:** 使用了哪些数据集？（如果提到，列出数据集名称）
4. **指标:** 使用了哪些评估指标？（如果提到，列出指标名称）
5. **关键结果:** 主要发现或结果是什么？
6. **局限性:** 论文提到的局限性或限制条件？
7. **假设:** 研究基于的假设或前提条件？
8. **未来工作:** 论文提到的未来研究方向？

请用简洁的中文回答，每个字段独立一行。如果某个字段在论文中没有信息，写"原文未明确说明"。
"""

        return prompt

    def _extract_evidence_from_sections(
        self,
        sections: list[Any],
        paper_id: str,
    ) -> list[dict[str, Any]]:
        """
        Extract evidence snippets from PDF sections.

        Args:
            sections: List of Section objects from parse_pdf().
            paper_id: Paper ID.

        Returns:
            List of evidence dictionaries with snippet, section, and page.
        """
        evidence = []

        for section in sections:
            # Create evidence snippet from each section
            # Truncate content to reasonable length
            snippet = section.content[:300]
            if len(section.content) > 300:
                snippet += "..."

            evidence_item = {
                "snippet": snippet,
                "section": section.heading,
            }

            # Add page number if available
            if section.page_number is not None:
                evidence_item["page"] = section.page_number

            evidence.append(evidence_item)

        return evidence
