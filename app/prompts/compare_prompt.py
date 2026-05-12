COMPARE_PROMPT = """你是一名科研综述助手。请根据多篇论文的结构化信息，生成结构化对比分析 JSON。

要求：
1. 只输出合法 JSON，不要输出 Markdown、解释或代码块。
2. 顶层字段必须包含：
   - overview: 字符串，总结多篇论文的整体关系与主要差异
   - aspects: 数组
3. aspects 中每个元素必须包含：
   - name: 从以下字段中选择一个：research_problem, method, backbone, dataset, metrics, strengths, limitations, scenarios, key_differences
   - summary: 该维度的总体总结
   - key_differences: 字符串数组，列出该维度的重要差异
   - per_paper: 对象，key 为 paper_id，value 为该论文在该维度上的简要描述；若原文未明确说明，填“未明确说明”
   - evidence: 数组，每个元素包含 paper_id, paper_title, section, snippet
4. 证据必须基于提供的论文信息，禁止编造；若某字段缺失，显式写“未明确说明”。
5. 输出应使用中文学术风格，保持克制，不夸大结论。

论文信息：
{papers}
"""


EXTRACTION_PROMPT = """你是一名科研论文信息抽取助手。请基于每篇论文给出的摘要与章节片段，输出每篇论文的结构化摘要 JSON。

要求：
1. 只输出合法 JSON，不要输出 Markdown、解释或代码块。
2. 顶层必须是对象，key 为 paper_id。
3. 每个 paper_id 对应的对象必须包含字段：
   - research_problem
   - method
   - backbone
   - dataset
   - metrics
   - strengths
   - limitations
   - scenarios
   - evidence
4. evidence 为数组，每个元素包含：
   - section
   - snippet
5. 所有字段使用中文学术风格总结；若原文未明确说明，填“未明确说明”。
6. evidence 只能引用提供内容中的原句或紧贴原句的短摘录，禁止编造。

论文信息：
{papers}
"""


def build_compare_prompt(papers_text: str) -> str:
    return COMPARE_PROMPT.format(papers=papers_text)


def build_extraction_prompt(papers_text: str) -> str:
    return EXTRACTION_PROMPT.format(papers=papers_text)
