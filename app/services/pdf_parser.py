import json
import logging
import os
import re
from datetime import date

import fitz  # PyMuPDF

from app.schemas import PaperParseResult, Section

logger = logging.getLogger(__name__)


SECTION_KEYWORDS = [
    "Abstract",
    "Introduction",
    "Related Work",
    "Methodology",
    "Method",
    "Experiments",
    "Experiment",
    "Results",
    "Discussion",
    "Conclusion",
    "References",
]


def generate_paper_id(upload_dir: str | None = None) -> str:
    today = date.today().strftime("%Y%m%d")
    if upload_dir and os.path.isdir(upload_dir):
        existing = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
        seq = len(existing)
    else:
        from app.config import settings

        md = settings.metadata_dir
        if os.path.isdir(md):
            parsed_files = [f for f in os.listdir(md) if f.endswith("_parsed.json")]
            seq = len(parsed_files)
        else:
            seq = 0
    return f"paper_{today}_{seq + 1:03d}"


def _extract_pages_text(doc: fitz.Document) -> list[str]:
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text.strip())
    return pages


def _extract_full_text(doc: fitz.Document) -> str:
    return "\n\n".join(_extract_pages_text(doc))


def _detect_title(text: str, doc: fitz.Document) -> str:
    # Try font-size–based detection on the first page
    if doc.page_count > 0:
        page = doc[0]
        blocks = page.get_text("dict").get("blocks", [])
        candidates = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                if not line_text or len(line_text) < 5 or len(line_text) > 200:
                    continue
                max_font = max(
                    (span["size"] for span in line["spans"] if span["text"].strip()),
                    default=0,
                )
                if max_font > 12:
                    candidates.append((max_font, line_text))
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            return candidates[0][1]

    # Fallback: first meaningful short line
    lines = text.strip().split("\n")
    for line in lines[:20]:
        stripped = line.strip()
        if (
            stripped
            and len(stripped) >= 5
            and not re.match(r"^(abstract|introduction)$", stripped, re.IGNORECASE)
        ):
            # Avoid lines that are clearly metadata
            if "," in stripped and len(stripped) < 30:
                continue
            return stripped
    return ""


def _extract_abstract(text: str) -> str:
    pattern = re.compile(
        r"\b(?:Abstract|ABSTRACT)\b",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return ""

    start = match.end()
    rest = text[start:]

    # Find the next section heading
    heading_pattern = re.compile(
        r"^\s*(?:\d+[\.\s]+|[IVX]+[\.\s]+)?("
        + "|".join(re.escape(kw) for kw in SECTION_KEYWORDS if kw.lower() != "abstract")
        + r")\b",
        re.IGNORECASE | re.MULTILINE,
    )
    end_match = heading_pattern.search(rest)
    if end_match:
        abstract_text = rest[: end_match.start()]
    else:
        abstract_text = rest[:2000]

    return abstract_text.strip()[:3000]


def _extract_sections(text: str, page_texts: list[str] | None = None) -> list[Section]:
    # Build a regex that matches section headings
    keywords_pattern = "|".join(
        re.escape(kw) for kw in SECTION_KEYWORDS if kw.lower() != "abstract"
    )
    heading_re = re.compile(
        r"(?:^|\n)"  # line start
        r"\s*"  # optional whitespace
        r"(?:\d+[\.\)]\s*|[IVX]+[\.\)]\s*)?"  # optional numbering
        r"(" + keywords_pattern + r")\b",  # keyword
        re.IGNORECASE,
    )

    matches = list(heading_re.finditer(text))
    if not matches:
        # Return whole text as one section
        return [Section(heading="全文", content=text.strip())]

    sections = []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        content_start = m.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[content_start:content_end].strip()
        if content:
            page_number = None
            if page_texts:
                for index, page_text in enumerate(page_texts, start=1):
                    if heading in page_text and content[:80].strip() in page_text:
                        page_number = index
                        break
            sections.append(
                Section(heading=heading, content=content, page_number=page_number)
            )

    return sections


def parse_pdf(filepath: str, paper_id: str) -> PaperParseResult:
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"PDF 文件不存在: {filepath}")

    try:
        doc = fitz.open(filepath)
    except Exception as e:
        raise ValueError(f"无法打开 PDF 文件 (可能已损坏或格式错误): {e}") from e

    try:
        page_texts = _extract_pages_text(doc)
        full_text = "\n\n".join(page_texts)
        if not full_text.strip():
            raise ValueError("PDF 文件无法提取到文本内容，可能为扫描版或图片型 PDF")

        title = _detect_title(full_text, doc)
        abstract = _extract_abstract(full_text)
        sections = _extract_sections(full_text, page_texts=page_texts)

        logger.info(
            "PDF parsed: %s, title=%s, sections=%d, chars=%d",
            paper_id,
            title,
            len(sections),
            len(full_text),
        )

        return PaperParseResult(
            paper_id=paper_id,
            title=title,
            abstract=abstract,
            sections=sections,
            full_text=full_text,
            pdf_path=filepath,
        )
    finally:
        doc.close()


def save_parse_result(result: PaperParseResult, metadata_dir: str) -> str:
    os.makedirs(metadata_dir, exist_ok=True)
    filename = f"{result.paper_id}_parsed.json"
    filepath = os.path.join(metadata_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2, ensure_ascii=False))
    return filepath


def load_parsed_result(paper_id: str, metadata_dir: str) -> dict:
    filepath = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"论文解析结果不存在: {filepath}，请先上传并解析 PDF")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def find_pdf_path(
    paper_id: str, upload_dir: str, metadata_dir: str | None = None
) -> str:
    if metadata_dir is None:
        from app.config import settings

        metadata_dir = settings.metadata_dir

    data = load_parsed_result(paper_id, metadata_dir)
    stored_path = data.get("pdf_path", "")
    if stored_path and os.path.isfile(stored_path):
        return stored_path

    # Fallback: scan upload_dir for any PDF
    pdfs = sorted([f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")])
    if pdfs:
        return os.path.join(upload_dir, pdfs[0])

    raise FileNotFoundError(f"论文 {paper_id} 的 PDF 文件不存在于 {upload_dir}")


def list_papers(metadata_dir: str) -> list[dict]:
    papers = []
    if not os.path.isdir(metadata_dir):
        return papers
    for fname in sorted(os.listdir(metadata_dir)):
        if fname.endswith("_parsed.json"):
            try:
                data = load_parsed_result(
                    fname.replace("_parsed.json", ""), metadata_dir
                )
                papers.append(
                    {
                        "paper_id": data.get("paper_id", ""),
                        "title": data.get("title", ""),
                        "abstract": data.get("abstract", "")[:200],
                    }
                )
            except Exception:
                continue
    return papers
