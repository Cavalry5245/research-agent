"""
Planner Agent

生成初始检索计划和候选选择计划，支持 LLM 和 deterministic fallback。
"""

import json
import logging
from datetime import datetime
from typing import Any

from app.research_pipeline import store
from app.research_pipeline.schemas import ResearchPlan
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Planner Agent 负责两个阶段的规划：
    1. Initial phase: 生成 normalized question、subquestions、queries、relevance criteria
    2. Candidate selection phase: 从候选论文中选择最多 max_reader_papers 篇

    LLM 不可用或失败时自动 fallback：
    - Initial phase: 使用原问题作为单个 query
    - Candidate selection: 按 citation_count 降序选择 top N
    """

    def __init__(self, db_path: str, llm_client: LLMClient | None = None):
        """
        Initialize PlannerAgent.

        Args:
            db_path: Path to SQLite database.
            llm_client: Optional LLM client. If None, creates default client.
        """
        self.db_path = db_path
        self.llm_client = llm_client
        if self.llm_client is None:
            try:
                self.llm_client = LLMClient()
            except ValueError:
                logger.warning("LLM client unavailable, will use fallback for all planning")
                self.llm_client = None

    def plan_initial(
        self,
        run_id: str,
        question: str,
        source_mode: str,
    ) -> ResearchPlan:
        """
        Generate initial research plan.

        尝试使用 LLM 生成结构化计划；失败时使用 deterministic fallback。

        Args:
            run_id: Research run ID.
            question: User's research question.
            source_mode: Source mode ("web_search", "zotero_only", "hybrid").

        Returns:
            ResearchPlan with initial phase planning data.
        """
        logger.info("PlannerAgent: Starting initial phase for run_id=%s", run_id)

        plan_data = self._generate_initial_plan_with_llm(question, source_mode)

        # Save plan to store
        plan_id = store.create_plan(
            db_path=self.db_path,
            run_id=run_id,
            phase="initial",
            plan_data=plan_data,
        )

        # Get the saved plan with version number
        plans = store.get_plans_by_run(self.db_path, run_id)
        saved_plan = next(p for p in plans if p["id"] == plan_id)

        # Convert to ResearchPlan schema
        return ResearchPlan(
            id=saved_plan["id"],
            run_id=saved_plan["run_id"],
            version=saved_plan["version"],
            phase=saved_plan["phase"],
            plan_data=saved_plan["plan_data"],
            created_at=datetime.fromisoformat(saved_plan["created_at"]),
        )

    def plan_candidate_selection(
        self,
        run_id: str,
        max_reader_papers: int,
    ) -> ResearchPlan:
        """
        Generate candidate selection plan.

        从已有的候选论文中选择最多 max_reader_papers 篇进行详细阅读。

        Args:
            run_id: Research run ID.
            max_reader_papers: Maximum papers to select for reader (3-15).

        Returns:
            ResearchPlan with candidate_selection phase planning data.
        """
        logger.info(
            "PlannerAgent: Starting candidate selection for run_id=%s, max_papers=%d",
            run_id,
            max_reader_papers,
        )

        # Get candidates from store
        candidates = store.get_candidates(self.db_path, run_id)

        if not candidates:
            logger.warning("No candidates found for run_id=%s", run_id)
            plan_data = {
                "selected_paper_ids": [],
                "reasoning": "No candidates available",
                "fallback_used": False,
            }
        else:
            plan_data = self._generate_selection_plan_with_llm(
                candidates, max_reader_papers
            )

        # Save plan to store
        plan_id = store.create_plan(
            db_path=self.db_path,
            run_id=run_id,
            phase="candidate_selection",
            plan_data=plan_data,
        )

        # Get the saved plan with version number
        plans = store.get_plans_by_run(self.db_path, run_id)
        saved_plan = next(p for p in plans if p["id"] == plan_id)

        # Convert to ResearchPlan schema
        return ResearchPlan(
            id=saved_plan["id"],
            run_id=saved_plan["run_id"],
            version=saved_plan["version"],
            phase=saved_plan["phase"],
            plan_data=saved_plan["plan_data"],
            created_at=datetime.fromisoformat(saved_plan["created_at"]),
        )

    def _generate_initial_plan_with_llm(
        self, question: str, source_mode: str
    ) -> dict[str, Any]:
        """
        尝试使用 LLM 生成初始计划，失败时 fallback。

        Returns:
            Plan data dict with normalized_question, queries, subquestions, criteria.
        """
        if self.llm_client is None:
            logger.info("LLM client unavailable, using fallback")
            return self._fallback_initial_plan(question)

        try:
            prompt = self._build_initial_plan_prompt(question, source_mode)
            response = self.llm_client.generate_text(prompt)

            # Try to parse JSON
            try:
                plan_data = json.loads(response)

                # Validate required fields
                required_fields = [
                    "normalized_question",
                    "queries",
                    "subquestions",
                    "relevance_criteria",
                ]
                if not all(field in plan_data for field in required_fields):
                    logger.warning("LLM response missing required fields, using fallback")
                    return self._fallback_initial_plan(question)

                # Add metadata
                plan_data["fallback_used"] = False
                logger.info("Initial plan generated successfully via LLM")
                return plan_data

            except json.JSONDecodeError as e:
                logger.warning("LLM response is not valid JSON: %s, using fallback", e)
                return self._fallback_initial_plan(question)

        except Exception as e:
            logger.warning("LLM call failed: %s, using fallback", e)
            return self._fallback_initial_plan(question)

    def _generate_selection_plan_with_llm(
        self, candidates: list[dict[str, Any]], max_reader_papers: int
    ) -> dict[str, Any]:
        """
        尝试使用 LLM 选择候选论文，失败时 fallback。

        Returns:
            Plan data dict with selected_paper_ids and reasoning.
        """
        if self.llm_client is None:
            logger.info("LLM client unavailable, using fallback selection")
            return self._fallback_selection_plan(candidates, max_reader_papers)

        try:
            prompt = self._build_selection_prompt(candidates, max_reader_papers)
            response = self.llm_client.generate_text(prompt)

            # Try to parse JSON
            try:
                plan_data = json.loads(response)

                # Validate and enforce max limit
                if "selected_paper_ids" not in plan_data:
                    logger.warning(
                        "LLM response missing selected_paper_ids, using fallback"
                    )
                    return self._fallback_selection_plan(candidates, max_reader_papers)

                selected_ids = plan_data["selected_paper_ids"][:max_reader_papers]
                plan_data["selected_paper_ids"] = selected_ids
                plan_data["fallback_used"] = False

                logger.info(
                    "Candidate selection generated successfully via LLM: %d papers selected",
                    len(selected_ids),
                )
                return plan_data

            except json.JSONDecodeError as e:
                logger.warning("LLM response is not valid JSON: %s, using fallback", e)
                return self._fallback_selection_plan(candidates, max_reader_papers)

        except Exception as e:
            logger.warning("LLM call failed: %s, using fallback", e)
            return self._fallback_selection_plan(candidates, max_reader_papers)

    def _fallback_initial_plan(self, question: str) -> dict[str, Any]:
        """
        Deterministic fallback for initial planning.

        使用原问题作为单个 query。
        """
        logger.info("Using fallback initial plan: original question as query")
        return {
            "normalized_question": question,
            "queries": [question],
            "subquestions": [],
            "relevance_criteria": [],
            "fallback_used": True,
        }

    def _fallback_selection_plan(
        self, candidates: list[dict[str, Any]], max_reader_papers: int
    ) -> dict[str, Any]:
        """
        Deterministic fallback for candidate selection.

        按 citation_count 降序选择 top N。
        """
        logger.info(
            "Using fallback selection: top %d by citation count", max_reader_papers
        )

        # Sort by citation_count (descending), then by year (descending)
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                c.get("citation_count") or 0,
                c.get("year") or 0,
            ),
            reverse=True,
        )

        # Select top N
        selected_ids = [c["paper_id"] for c in sorted_candidates[:max_reader_papers]]

        return {
            "selected_paper_ids": selected_ids,
            "reasoning": f"Fallback selection: top {len(selected_ids)} papers by citation count",
            "fallback_used": True,
        }

    def _build_initial_plan_prompt(self, question: str, source_mode: str) -> str:
        """构建初始规划的 LLM prompt"""
        return f"""你是一个学术研究规划助手。用户提出了一个研究问题，你需要生成一个检索计划。

**用户问题：**
{question}

**检索模式：** {source_mode}

请生成一个 JSON 格式的检索计划，包含以下字段：

1. **normalized_question**: 标准化后的研究问题（更清晰、更具体）
2. **subquestions**: 将主问题分解为 2-4 个子问题（list of strings）
3. **queries**: 生成 3-5 个检索查询词（适合学术搜索引擎）（list of strings）
4. **relevance_criteria**: 论文相关性判断标准（3-5 条）（list of strings）

**输出格式：** 纯 JSON，不要有其他文字。

示例：
{{
  "normalized_question": "Transformer 模型在 2020 年后有哪些架构改进？",
  "subquestions": [
    "Transformer 的注意力机制有哪些优化方法？",
    "哪些模型解决了 Transformer 的计算效率问题？"
  ],
  "queries": [
    "transformer architecture improvements 2020-2024",
    "efficient attention mechanisms",
    "linear transformers"
  ],
  "relevance_criteria": [
    "论文必须讨论 Transformer 架构",
    "发表时间在 2019 年之后",
    "包含实验结果"
  ]
}}

现在，请为用户的问题生成检索计划："""

    def _build_selection_prompt(
        self, candidates: list[dict[str, Any]], max_reader_papers: int
    ) -> str:
        """构建候选选择的 LLM prompt"""

        # Build candidate summary
        candidate_summaries = []
        for i, c in enumerate(candidates, 1):
            summary = f"{i}. paper_id: {c['paper_id']}\n"
            summary += f"   title: {c['title']}\n"
            summary += f"   authors: {', '.join(c.get('authors', []))}\n"
            summary += f"   year: {c.get('year', 'N/A')}\n"
            summary += f"   venue: {c.get('venue', 'N/A')}\n"
            summary += f"   citation_count: {c.get('citation_count', 0)}\n"
            if c.get("abstract"):
                abstract_preview = c["abstract"][:200] + "..." if len(c["abstract"]) > 200 else c["abstract"]
                summary += f"   abstract: {abstract_preview}\n"
            candidate_summaries.append(summary)

        candidates_text = "\n".join(candidate_summaries)

        return f"""你是一个学术论文筛选助手。现在有 {len(candidates)} 篇候选论文，请从中选择最相关的 **最多 {max_reader_papers} 篇** 进行详细阅读。

**候选论文列表：**
{candidates_text}

**选择标准：**
- 相关性（标题和摘要与研究问题的匹配度）
- 影响力（引用数）
- 时效性（发表年份）
- 多样性（覆盖不同方法/角度）

请生成一个 JSON 格式的选择计划，包含以下字段：

1. **selected_paper_ids**: 选中的 paper_id 列表（最多 {max_reader_papers} 个）（list of strings）
2. **reasoning**: 选择理由（简要说明为什么选择这些论文）（string）

**输出格式：** 纯 JSON，不要有其他文字。

示例：
{{
  "selected_paper_ids": ["paper_0", "paper_1", "paper_2"],
  "reasoning": "选择了引用数最高的 3 篇论文，覆盖了效率优化和架构改进两个方向"
}}

现在，请选择论文："""
