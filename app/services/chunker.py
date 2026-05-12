from app.schemas import Chunk, PaperParseResult

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100
MIN_CHUNK_CHARS = 20


def _sliding_window(text: str, chunk_size: int, chunk_overlap: int) -> list[tuple[int, int, str]]:
    text = text.strip()
    if not text:
        return []
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            stripped_start = text[start:end].find(chunk_text)
            absolute_start = start + max(stripped_start, 0)
            absolute_end = absolute_start + len(chunk_text)
            chunks.append((absolute_start, absolute_end, chunk_text))
        if end >= len(text):
            break
        start = end - chunk_overlap
    return chunks


def chunk_paper(
    parsed: PaperParseResult,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    seq = 0

    for section in parsed.sections:
        if not section.content or len(section.content.strip()) < MIN_CHUNK_CHARS:
            continue

        text_parts = _sliding_window(section.content, chunk_size, chunk_overlap)
        for chunk_start, chunk_end, part in text_parts:
            if len(part) < MIN_CHUNK_CHARS:
                continue
            seq += 1
            chunk_id = f"{parsed.paper_id}_chunk_{seq:04d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    paper_id=parsed.paper_id,
                    title=parsed.title,
                    section=section.heading,
                    content=part,
                    page_number=section.page_number,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end,
                )
            )

    # If no sections produced valid chunks, fall back to full_text
    if not chunks and parsed.full_text.strip():
        text_parts = _sliding_window(parsed.full_text, chunk_size, chunk_overlap)
        for chunk_start, chunk_end, part in text_parts:
            if len(part) < MIN_CHUNK_CHARS:
                continue
            seq += 1
            chunk_id = f"{parsed.paper_id}_chunk_{seq:04d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    paper_id=parsed.paper_id,
                    title=parsed.title,
                    section="全文",
                    content=part,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end,
                )
            )

    return chunks
