"""Prompt templates for the LLM-backed evaluation judges (Phase 2 P1)."""

ANSWER_JUDGE_PROMPT = """你是一名严格的科研论文问答评测员。你的任务是对比【模型答案】与【参考答案】，判断模型答案是否在语义上正确、完整地回答了问题。

评分规则：
- 1.0：完全正确，覆盖参考答案的全部要点，无事实错误
- 0.7-0.9：基本正确，覆盖大部分要点，可能有小遗漏或表述差异
- 0.4-0.6：部分正确，覆盖少数要点或有部分模糊/不准确
- 0.1-0.3：大部分错误或基本未回答问题
- 0.0：完全错误、空答案、答非所问、明显幻觉

注意：
- 模型答案可能比参考答案更详细（包含合理推理或补充说明），这不扣分。
- 重点判断**核心事实**和**关键论点**是否对齐，不要纠结表述方式或语言风格。
- 如果参考答案是"原文未明确说明。"，则模型应当 abstain（明确表示原文未提及）。此时如果模型也表示原文未提及，给 1.0；如果模型强行编造答案，给 0.0。

【问题】
{question}

【参考答案】
{expected_answer}

【模型答案】
{predicted_answer}

请以下面 JSON 格式输出（不要任何额外文本）：
{{"score": <0.0-1.0>, "passed": <true/false>, "reason": "<一句话评价>", "missing_points": ["<参考答案中未被覆盖的要点>"], "incorrect_points": ["<模型答案中的错误>"]}}

passed 的判断标准：score >= 0.5 即为 true。
"""


CITATION_JUDGE_PROMPT = """你是一名严格的引用质量评测员。你的任务是判断【模型引用】是否合理支撑了【模型答案】。

评分规则：
- 1.0：引用的论文 ID、章节都正确指向能支撑答案的位置
- 0.7-0.9：大部分引用合理，可能有 1 个边缘相关
- 0.4-0.6：部分引用合理，部分引用偏离主题
- 0.1-0.3：大部分引用与答案/问题不相关
- 0.0：完全无引用、引用完全错误、或答案不需要引用却乱引

期望来源章节（论文中实际相关的章节）：{expected_sections}
期望论文 ID：{expected_paper_id}

【问题】
{question}

【模型答案】
{predicted_answer}

【模型引用】
{citations_text}

请以下面 JSON 格式输出（不要任何额外文本）：
{{"score": <0.0-1.0>, "passed": <true/false>, "reason": "<一句话评价>", "irrelevant_citations": ["<被引用但不相关的来源>"], "missing_evidence": ["<答案中需要支撑但没有引用的论点>"]}}

passed 的判断标准：score >= 0.5 即为 true。
"""


def build_answer_judge_prompt(
    question: str, expected_answer: str, predicted_answer: str
) -> str:
    return ANSWER_JUDGE_PROMPT.format(
        question=(question or "").strip(),
        expected_answer=(expected_answer or "").strip() or "(空)",
        predicted_answer=(predicted_answer or "").strip() or "(空)",
    )


def build_citation_judge_prompt(
    question: str,
    predicted_answer: str,
    citations: list[dict],
    expected_sections: list[str],
    expected_paper_id: str | None,
) -> str:
    if citations:
        citation_lines = []
        for i, c in enumerate(citations, 1):
            paper_id = c.get("paper_id", "?")
            section = c.get("section", "?")
            score = c.get("score")
            score_str = (
                f" (score={score:.3f})" if isinstance(score, (int, float)) else ""
            )
            citation_lines.append(
                f"  {i}. paper_id={paper_id} | section={section}{score_str}"
            )
        citations_text = "\n".join(citation_lines)
    else:
        citations_text = "(无引用)"
    return CITATION_JUDGE_PROMPT.format(
        question=(question or "").strip(),
        predicted_answer=(predicted_answer or "").strip() or "(空)",
        citations_text=citations_text,
        expected_sections=(
            ", ".join(expected_sections) if expected_sections else "(未指定)"
        ),
        expected_paper_id=expected_paper_id or "(未指定)",
    )
