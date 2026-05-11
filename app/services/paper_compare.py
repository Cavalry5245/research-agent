import logging
from datetime import datetime

from app.services.llm_client import LLMClient
from app.services.pdf_parser import load_parsed_result
from app.prompts.compare_prompt import build_compare_prompt

logger = logging.getLogger(__name__)


def _build_paper_summary(parsed: dict) -> str:
    lines = [
        f"### {parsed.get('title', '未知')}",
        f"- 摘要: {parsed.get('abstract', '无')[:500]}",
    ]
    for sec in parsed.get("sections", []):
        heading = sec.get("heading", "")
        content = sec.get("content", "")[:400]
        if content:
            lines.append(f"- {heading}: {content}")
    return "\n".join(lines)


def compare_papers(
    paper_ids: list[str],
    metadata_dir: str,
    llm_client: LLMClient | None = None,
) -> str:
    if len(paper_ids) < 2:
        raise ValueError("请选择至少 2 篇论文进行对比")
    if len(paper_ids) > 5:
        raise ValueError("最多支持 5 篇论文对比")

    if llm_client is None:
        llm_client = LLMClient()

    summaries = []
    for pid in paper_ids:
        data = load_parsed_result(pid, metadata_dir)
        summaries.append(_build_paper_summary(data))

    papers_text = "\n\n---\n\n".join(summaries)
    prompt = build_compare_prompt(papers_text)

    logger.info("Comparing %d papers", len(paper_ids))
    result = llm_client.generate_text(prompt)
    return result


def save_compare_result(markdown: str, note_dir: str) -> str:
    import os
    os.makedirs(note_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(note_dir, f"compare_{ts}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)
    return filepath
