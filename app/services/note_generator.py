import logging
import os
import time

from app.services.llm_client import LLMClient
from app.services.pdf_parser import load_parsed_result
from app.prompts.paper_note_prompt import build_note_prompt

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 8000


def _build_paper_content(parsed: dict) -> str:
    sections = parsed.get("sections", [])
    abstract = parsed.get("abstract", "")
    full_text = parsed.get("full_text", "")

    if len(full_text) <= MAX_CONTENT_CHARS:
        return full_text

    parts = []
    if abstract:
        parts.append(f"摘要：\n{abstract}")

    for sec in sections:
        heading = sec.get("heading", "")
        content = sec.get("content", "")
        if content:
            parts.append(f"## {heading}\n{content}")

    combined = "\n\n".join(parts)
    if len(combined) > MAX_CONTENT_CHARS:
        combined = combined[:MAX_CONTENT_CHARS] + "\n\n[内容过长，已截断]"

    return combined


def generate_note(
    paper_id: str,
    metadata_dir: str | None = None,
    llm_client: LLMClient | None = None,
) -> str:
    if metadata_dir is None:
        from app.config import settings
        metadata_dir = settings.metadata_dir

    if llm_client is None:
        llm_client = LLMClient()

    parsed = load_parsed_result(paper_id, metadata_dir)
    title = parsed.get("title", "未知标题")
    paper_content = _build_paper_content(parsed)
    prompt = build_note_prompt(title, paper_content)

    logger.info("Generating note for %s, content_chars=%d", paper_id, len(paper_content))
    llm_start = time.perf_counter()
    markdown = llm_client.generate_text(prompt)
    llm_seconds = time.perf_counter() - llm_start

    _emit_note_event(paper_id=paper_id, llm_time=llm_seconds, content_length=len(markdown or ""))
    return markdown


def _emit_note_event(paper_id: str, llm_time: float, content_length: int) -> None:
    """Best-effort analytics emit for note generation."""
    try:
        from app.analytics import get_collector

        get_collector().log_note(paper_id=paper_id, llm_time=llm_time, content_length=content_length)
    except Exception as exc:
        logger.debug("Analytics emit skipped: %s", exc)
