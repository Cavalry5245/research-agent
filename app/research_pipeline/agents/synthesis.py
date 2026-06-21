"""
Synthesis Agent

生成固定 8 节 Markdown 研究报告，支持 LLM 和 deterministic fallback。
"""

import logging
from typing import Any

from app.research_pipeline.schemas import PaperCard
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SynthesisAgent:
    """
    Synthesis Agent 负责根据 plan 和 PaperCards 生成研究报告。

    报告包含固定 8 个章节：
    1. Research Question
    2. Methodology Landscape
    3. Dataset And Metric Comparison
    4. SOTA And Key Results
    5. Limitations And Failure Modes
    6. Conflicts Or Inconsistent Findings
    7. Research Gaps
    8. References

    LLM 不可用或失败时自动 fallback 到 deterministic skeleton。
    """

    def __init__(self, db_path: str, llm_client: LLMClient | None = None):
        """
        Initialize SynthesisAgent.

        Args:
            db_path: Path to SQLite database.
            llm_client: Optional LLM client. If None, uses fallback skeleton.
        """
        self.db_path = db_path
        self.llm_client = llm_client

    def execute(
        self,
        initial_plan: dict[str, Any],
        candidate_selection_plan: dict[str, Any],
        paper_cards: list[PaperCard],
        evidence: list[dict[str, Any]],
    ) -> str:
        """
        生成研究报告 Markdown。

        Args:
            initial_plan: 初始计划（包含 normalized_question、subquestions 等）
            candidate_selection_plan: 候选选择计划（包含 selected_paper_ids）
            paper_cards: PaperCards 列表（已经过 Reader 处理）
            evidence: Evidence 列表

        Returns:
            Markdown 格式的研究报告
        """
        if self.llm_client is None:
            logger.info("LLM unavailable, generating skeleton report")
            return self._generate_skeleton(initial_plan, paper_cards)

        try:
            logger.info("Generating report with LLM for %d papers", len(paper_cards))
            return self._generate_with_llm(
                initial_plan, candidate_selection_plan, paper_cards, evidence
            )
        except Exception as e:
            logger.warning("LLM synthesis failed: %s, falling back to skeleton", e)
            return self._generate_skeleton(initial_plan, paper_cards)

    def _generate_with_llm(
        self,
        initial_plan: dict[str, Any],
        candidate_selection_plan: dict[str, Any],
        paper_cards: list[PaperCard],
        evidence: list[dict[str, Any]],
    ) -> str:
        """使用 LLM 生成完整报告。"""
        # Build context from paper cards
        papers_context = self._build_papers_context(paper_cards)

        normalized_question = initial_plan.get("normalized_question", "研究问题")
        subquestions = initial_plan.get("subquestions", [])

        prompt = f"""你是一个学术研究报告生成助手。请根据以下信息生成一份严谨的研究综述报告。

研究问题: {normalized_question}

子问题:
{self._format_list(subquestions)}

已阅读的论文信息:
{papers_context}

请生成一份包含以下 8 个章节的 Markdown 格式报告，使用中文撰写，学术风格：

## 1. Research Question
- 阐述研究问题和背景

## 2. Methodology Landscape
- 总结主要方法和技术路线
- 引用论文时使用 [CITE:paper_id] 格式

## 3. Dataset And Metric Comparison
- 比较数据集和评估指标
- 列表形式呈现

## 4. SOTA And Key Results
- 总结最新成果和关键结果
- 使用 [CITE:paper_id] 引用

## 5. Limitations And Failure Modes
- 讨论局限性和失败模式

## 6. Conflicts Or Inconsistent Findings
- 指出不一致的发现（如果有）

## 7. Research Gaps
- 识别研究空白

## 8. References
- 列出所有引用的论文
- 格式: [paper_id] 作者 (年份). 标题. 会议/期刊.

要求:
1. 只引用提供的论文（paper_cards）
2. 使用 [CITE:paper_id] 格式进行引用
3. 不要编造信息，如果信息不足请注明"原文未明确说明"
4. 保持学术严谨性

现在请生成完整报告:"""

        report_md = self.llm_client.generate_text(prompt)
        return report_md

    def _generate_skeleton(
        self, initial_plan: dict[str, Any], paper_cards: list[PaperCard]
    ) -> str:
        """生成 deterministic skeleton 报告（LLM 不可用时）。"""
        normalized_question = initial_plan.get("normalized_question", "研究问题未明确")

        skeleton = f"""# Research Report

> **注意**: 本报告由自动骨架生成，LLM 不可用。需要人工综合完成各章节内容。

## 1. Research Question

{normalized_question}

## 2. Methodology Landscape

[自动综合不可用] 需要基于以下论文人工总结方法论全景：

{self._list_papers_for_skeleton(paper_cards, include_methods=True)}

## 3. Dataset And Metric Comparison

[自动综合不可用] 需要基于以下信息人工比较：

{self._list_datasets_and_metrics(paper_cards)}

## 4. SOTA And Key Results

[自动综合不可用] 需要基于以下结果人工总结：

{self._list_key_results(paper_cards)}

## 5. Limitations And Failure Modes

[自动综合不可用] 需要基于以下限制人工分析：

{self._list_limitations(paper_cards)}

## 6. Conflicts Or Inconsistent Findings

[自动综合不可用] 需要人工识别不一致之处。

## 7. Research Gaps

[自动综合不可用] 需要基于以下未来工作方向人工总结研究空白：

{self._list_future_work(paper_cards)}

## 8. References

{self._generate_references(paper_cards)}
"""
        return skeleton

    def _build_papers_context(self, paper_cards: list[PaperCard]) -> str:
        """构建论文上下文用于 LLM prompt。"""
        if not paper_cards:
            return "暂无论文信息。"

        context_parts = []
        for card in paper_cards:
            authors = card.bibliographic_metadata.get("authors", [])
            year = card.bibliographic_metadata.get("year", "未知")
            venue = card.bibliographic_metadata.get("venue", "未知")

            authors_str = ", ".join(authors[:3])  # 限制作者数量
            if len(authors) > 3:
                authors_str += " et al."

            context = f"""
[{card.paper_id}]
标题: {card.title}
作者: {authors_str}
年份: {year}
会议/期刊: {venue}
研究问题: {card.research_problem or "未提取"}
方法: {card.method or "未提取"}
数据集: {", ".join(card.datasets) if card.datasets else "未提取"}
指标: {", ".join(card.metrics) if card.metrics else "未提取"}
关键结果: {"; ".join(card.key_results) if card.key_results else "未提取"}
局限性: {"; ".join(card.limitations) if card.limitations else "未提取"}
未来工作: {"; ".join(card.future_work) if card.future_work else "未提取"}
"""
            context_parts.append(context.strip())

        return "\n\n".join(context_parts)

    def _list_papers_for_skeleton(
        self, paper_cards: list[PaperCard], include_methods: bool = False
    ) -> str:
        """列出论文（skeleton 用）。"""
        if not paper_cards:
            return "暂无论文。"

        lines = []
        for card in paper_cards:
            line = f"- [CITE:{card.paper_id}] {card.title}"
            if include_methods and card.method:
                line += f"\n  - 方法: {card.method}"
            lines.append(line)

        return "\n".join(lines)

    def _list_datasets_and_metrics(self, paper_cards: list[PaperCard]) -> str:
        """列出数据集和指标。"""
        if not paper_cards:
            return "暂无数据。"

        lines = []
        for card in paper_cards:
            if card.datasets or card.metrics:
                lines.append(f"- [CITE:{card.paper_id}]")
                if card.datasets:
                    lines.append(f"  - 数据集: {', '.join(card.datasets)}")
                if card.metrics:
                    lines.append(f"  - 指标: {', '.join(card.metrics)}")

        return "\n".join(lines) if lines else "暂无数据集和指标信息。"

    def _list_key_results(self, paper_cards: list[PaperCard]) -> str:
        """列出关键结果。"""
        if not paper_cards:
            return "暂无结果。"

        lines = []
        for card in paper_cards:
            if card.key_results:
                lines.append(f"- [CITE:{card.paper_id}]")
                for result in card.key_results:
                    lines.append(f"  - {result}")

        return "\n".join(lines) if lines else "暂无关键结果信息。"

    def _list_limitations(self, paper_cards: list[PaperCard]) -> str:
        """列出局限性。"""
        if not paper_cards:
            return "暂无限制。"

        lines = []
        for card in paper_cards:
            if card.limitations:
                lines.append(f"- [CITE:{card.paper_id}]")
                for limitation in card.limitations:
                    lines.append(f"  - {limitation}")

        return "\n".join(lines) if lines else "暂无局限性信息。"

    def _list_future_work(self, paper_cards: list[PaperCard]) -> str:
        """列出未来工作方向。"""
        if not paper_cards:
            return "暂无未来工作方向。"

        lines = []
        for card in paper_cards:
            if card.future_work:
                lines.append(f"- [CITE:{card.paper_id}]")
                for work in card.future_work:
                    lines.append(f"  - {work}")

        return "\n".join(lines) if lines else "暂无未来工作方向信息。"

    def _generate_references(self, paper_cards: list[PaperCard]) -> str:
        """生成参考文献列表（只包含进入 Reader 的论文）。"""
        if not paper_cards:
            return "暂无参考文献。"

        refs = []
        for card in paper_cards:
            authors = card.bibliographic_metadata.get("authors", [])
            year = card.bibliographic_metadata.get("year", "n.d.")
            venue = card.bibliographic_metadata.get("venue", "")

            # Format authors
            if not authors:
                authors_str = "Unknown"
            elif len(authors) == 1:
                authors_str = authors[0]
            elif len(authors) == 2:
                authors_str = f"{authors[0]} and {authors[1]}"
            else:
                authors_str = f"{authors[0]} et al."

            # Format reference
            ref = f"[{card.paper_id}] {authors_str} ({year}). {card.title}."
            if venue:
                ref += f" {venue}."

            refs.append(ref)

        return "\n".join(refs)

    def _format_list(self, items: list[str]) -> str:
        """格式化列表为 Markdown。"""
        if not items:
            return "暂无"
        return "\n".join(f"- {item}" for item in items)
