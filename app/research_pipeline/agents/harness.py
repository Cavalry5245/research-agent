"""
Harness Agent

Rule-first verification of report claims against PaperCards and evidence.
"""

import logging
import re
from typing import Any

from app.research_pipeline.schemas import PaperCard, ReportClaim

logger = logging.getLogger(__name__)


class HarnessAgent:
    """
    Harness Agent 负责校验报告中的 claims。

    规则：
    1. 没有 citation 的 claim → unverified
    2. citation id 不在 PaperCards 中 → unverified
    3. 数字型 claim 缺少 evidence → numeric_trace_missing
    4. evidence 仅来自 abstract-only PaperCard → 最高 weak
    5. Harness 不修改报告原文，只返回 ReportClaim 列表
    """

    def __init__(self):
        """Initialize HarnessAgent."""
        pass

    def execute(
        self,
        report_markdown: str,
        paper_cards: list[PaperCard],
        evidence: list[dict[str, Any]],
    ) -> list[ReportClaim]:
        """
        验证报告中的 claims。

        Args:
            report_markdown: Markdown 格式的研究报告
            paper_cards: PaperCards 列表
            evidence: Evidence 列表

        Returns:
            ReportClaim 对象列表，包含 verification_status 和 verification_reason
        """
        if not report_markdown.strip():
            return []

        # Extract claims from report
        claims = self._extract_claims(report_markdown)

        if not claims:
            return []

        # Build lookup sets
        valid_paper_ids = {card.paper_id for card in paper_cards}
        abstract_only_ids = {
            card.paper_id
            for card in paper_cards
            if card.extraction_mode == "abstract_only"
        }
        evidence_map = self._build_evidence_map(evidence)

        # Validate each claim
        validated_claims = []
        for claim in claims:
            verified_claim = self._validate_claim(
                claim, valid_paper_ids, abstract_only_ids, evidence_map
            )
            validated_claims.append(verified_claim)

        return validated_claims

    def _extract_claims(self, report_markdown: str) -> list[ReportClaim]:
        """
        从报告中提取 claims。

        提取逻辑：
        - 识别 ## 2, 3, 4, 5, 7 章节（主要内容章节）
        - 提取每个句子作为潜在 claim
        - 解析 [CITE:paper_id] 引用
        - 判断 claim 类型
        """
        claims = []

        # Define section patterns
        section_patterns = {
            "method": r"##\s*2\.\s*Methodology Landscape",
            "dataset": r"##\s*3\.\s*Dataset And Metric Comparison",
            "result": r"##\s*4\.\s*SOTA And Key Results",
            "limitation": r"##\s*5\.\s*Limitations And Failure Modes",
            "gap": r"##\s*7\.\s*Research Gaps",
        }

        # Extract claims by section
        for claim_type, pattern in section_patterns.items():
            section_match = re.search(pattern, report_markdown, re.IGNORECASE)
            if not section_match:
                continue

            # Find section content (until next ## or end)
            start_pos = section_match.end()
            next_section = re.search(r"\n##\s+\d+\.", report_markdown[start_pos:])
            if next_section:
                end_pos = start_pos + next_section.start()
            else:
                end_pos = len(report_markdown)

            section_content = report_markdown[start_pos:end_pos]

            # Extract sentences as claims
            sentences = self._split_sentences(section_content)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence or len(sentence) < 10:
                    continue

                # Skip list markers and empty lines
                if sentence.startswith("-") or sentence.startswith("*"):
                    sentence = sentence[1:].strip()

                if not sentence:
                    continue

                # Parse citations
                citation_ids = self._parse_citations(sentence)

                # Create claim
                claim = ReportClaim(
                    claim_text=sentence,
                    claim_type=claim_type,
                    citation_ids=citation_ids,
                    evidence_ids=[],
                    verification_status="unverified",  # Will be updated
                    verification_reason="",
                )
                claims.append(claim)

        return claims

    def _split_sentences(self, text: str) -> list[str]:
        """
        将文本分割为句子。

        简单规则：按句号、问号、感叹号分割，但不在数字后面分割。
        """
        # Remove markdown links but preserve citation format [CITE:paper_id]
        text = re.sub(r"\[(?!CITE:).*?\]\(.*?\)", "", text)  # Remove links, keep citations
        text = re.sub(r"[#*`]", "", text)  # Remove markdown markers but keep underscores

        # Split by sentence endings, but not after numbers (e.g., 85.3% should not split)
        # Use negative lookbehind to avoid splitting after digits
        sentences = re.split(r"(?<!\d)[。？！]|(?<!\d)[.?!](?=\s|$)", text)
        return [s.strip() for s in sentences if s.strip()]

    def _parse_citations(self, text: str) -> list[str]:
        """
        解析 [CITE:paper_id] 引用。

        Returns:
            paper_id 列表
        """
        # Support paper IDs with letters, digits, underscores, dots, hyphens, and colons
        # Examples: paper_1, 2103.12345, arxiv:2103.12345, paper-001
        pattern = r"\[CITE:([a-zA-Z0-9_.\-:]+)\]"
        matches = re.findall(pattern, text)
        return matches

    def _build_evidence_map(
        self, evidence: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        构建 paper_id -> evidence 列表的映射。
        """
        evidence_map: dict[str, list[dict[str, Any]]] = {}
        for ev in evidence:
            paper_id = ev.get("paper_id", "")
            if not paper_id:
                continue
            if paper_id not in evidence_map:
                evidence_map[paper_id] = []
            evidence_map[paper_id].append(ev)
        return evidence_map

    def _validate_claim(
        self,
        claim: ReportClaim,
        valid_paper_ids: set[str],
        abstract_only_ids: set[str],
        evidence_map: dict[str, list[dict[str, Any]]],
    ) -> ReportClaim:
        """
        验证单个 claim。

        规则：
        1. 无引用 → unverified
        2. 引用的 paper_id 不在 valid_paper_ids → unverified
        3. result 类型且包含数字但无 evidence → numeric_trace_missing
        4. evidence 来自 abstract_only → weak
        5. 其他有效引用 + evidence → supported
        """
        # Rule 1: No citations
        if not claim.citation_ids:
            claim.verification_status = "unverified"
            claim.verification_reason = "没有引用来源"
            return claim

        # Rule 2: Invalid citations
        invalid_citations = [
            cid for cid in claim.citation_ids if cid not in valid_paper_ids
        ]
        if invalid_citations:
            claim.verification_status = "unverified"
            claim.verification_reason = f"引用的论文不在 PaperCards 中: {', '.join(invalid_citations)}"
            return claim

        # Check if numeric claim
        is_numeric = self._is_numeric_claim(claim.claim_text)

        # Rule 3: Numeric claim without evidence
        if claim.claim_type == "result" and is_numeric:
            # Check if any cited paper has evidence
            has_evidence = any(
                cid in evidence_map for cid in claim.citation_ids
            )
            if not has_evidence:
                claim.verification_status = "numeric_trace_missing"
                claim.verification_reason = "数字型结果缺少 evidence 支持"
                return claim

            # Has evidence - mark evidence_ids
            for cid in claim.citation_ids:
                if cid in evidence_map:
                    for ev in evidence_map[cid]:
                        # Simple match: if evidence text matches claim
                        ev_id = f"{cid}_ev_{len(claim.evidence_ids)}"
                        claim.evidence_ids.append(ev_id)

        # Rule 4: Abstract-only evidence
        all_abstract_only = all(
            cid in abstract_only_ids for cid in claim.citation_ids
        )
        if all_abstract_only:
            claim.verification_status = "weak"
            claim.verification_reason = "所有引用来源均为 abstract-only 模式，证据强度有限"
            return claim

        # Rule 5: Valid citations with full PDF
        claim.verification_status = "supported"
        claim.verification_reason = "引用来源有效且为完整 PDF 模式"

        # If has evidence, note it
        if claim.evidence_ids:
            claim.verification_reason += f"，找到 {len(claim.evidence_ids)} 条 evidence"

        return claim

    def _is_numeric_claim(self, text: str) -> bool:
        """
        判断 claim 是否包含数字（百分比、小数等）。
        """
        # Match percentage, decimal numbers, or integers with units
        pattern = r"\d+\.?\d*\s*%|\d+\.?\d+\s*(accuracy|precision|recall|F1|AUC)"
        return bool(re.search(pattern, text, re.IGNORECASE))

    def get_summary(self, claims: list[ReportClaim]) -> dict[str, int]:
        """
        按 verification_status 统计 claims。

        Returns:
            {status: count} 字典
        """
        summary: dict[str, int] = {}
        for claim in claims:
            status = claim.verification_status
            summary[status] = summary.get(status, 0) + 1
        return summary
