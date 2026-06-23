import json
import logging
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

from app.schemas import DocumentElement, PaperParseResult, PdfProfile, Section

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


TITLE_BLOCKLIST_PATTERNS = [
    r"^(abstract|introduction|contents?)$",
    r"^(arxiv|doi)\s*:",
    r"^(ph\.?d\.?|master'?s?)\b",
    r"^(?:\u535a\u58eb|\u7855\u58eb).{0,10}(?:\u5b66\u4f4d\u8bba\u6587|\u8bba\u6587)$",
    r"^(submitted|accepted|published|received)\b",
]

TITLE_BLOCKLIST_EXACT = {
    "remote sensing",
    "ieee transactions on pattern analysis and machine intelligence",
    "computer vision and pattern recognition",
}


def _normalize_title_candidate(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip(" \t\r\n-–—|:;,.")
    normalized = normalized.replace("\ufb01", "fi").replace("\ufb02", "fl")
    return normalized.strip()


def _filename_title_candidate(filepath: str) -> str:
    stem = Path(filepath).stem
    stem = re.sub(r"__new$", "", stem, flags=re.IGNORECASE)
    stem = stem.replace("_", " ").replace("-", " ")
    stem = re.sub(r"\s+", " ", stem)
    return _normalize_title_candidate(stem)


def _looks_like_author_line(text: str) -> bool:
    lowered = text.lower()
    if "@" in lowered:
        return True
    if re.search(r"\b(and|et al\.?)\b", lowered) and "," in text:
        return True
    if len(text.split(",")) >= 2 and len(text.split()) <= 12:
        return True
    return False


def _looks_like_metadata_line(text: str) -> bool:
    lowered = text.lower()
    if lowered in TITLE_BLOCKLIST_EXACT:
        return True
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in TITLE_BLOCKLIST_PATTERNS):
        return True
    if re.fullmatch(r"[\d\s:/.\-]+", text):
        return True
    if re.search(r"\b\d{4}\b", text) and re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", lowered
    ):
        return True
    if re.search(r"\b(vol\.?|no\.?|pp\.?)\b", lowered):
        return True
    if re.search(
        r"\b(university|school of|department of)\b|(?:\u5b66\u9662|\u5927\u5b66|\u7814\u7a76\u6240)",
        lowered,
    ):
        return True
    return False


def _score_title_candidate(
    text: str,
    *,
    source: str,
    font_size: float = 0.0,
    y0: float = 9999.0,
) -> float:
    candidate = _normalize_title_candidate(text)
    if not candidate:
        return -1000.0
    if len(candidate) < 8 or len(candidate) > 240:
        return -1000.0
    if _looks_like_metadata_line(candidate):
        return -1000.0

    score = 0.0
    word_count = len(candidate.split())

    if 12 <= len(candidate) <= 180:
        score += 20
    if 3 <= word_count <= 24:
        score += 18
    if y0 <= 220:
        score += 18
    if not candidate.islower():
        score += 8
    if re.search(r"[A-Z]", candidate) or re.search(r"[\u4e00-\u9fff]", candidate):
        score += 8
    if len(re.findall(r"[A-Za-z]", candidate)) >= 12:
        score += 8
    if font_size > 0:
        score += min(font_size, 30) * 1.6

    if source == "metadata":
        score += 14
    elif source == "cluster":
        score += 18
    elif source == "line":
        score += 8
    elif source == "filename":
        score += 3

    if _looks_like_author_line(candidate):
        score -= 30
    if candidate.count(":") >= 2:
        score -= 12
    if re.search(r"\b(arxiv|doi|issn)\b", candidate, re.IGNORECASE):
        score -= 30
    if re.fullmatch(r"[A-Za-z][A-Za-z\s]{0,30}", candidate) and candidate.islower():
        score -= 20

    return score


def _extract_title_candidates(doc: fitz.Document, filepath: str) -> list[dict[str, float | str]]:
    candidates: list[dict[str, float | str]] = []

    metadata_title = _normalize_title_candidate((doc.metadata or {}).get("title", ""))
    if metadata_title:
        candidates.append(
            {"text": metadata_title, "source": "metadata", "font_size": 0.0, "y0": 0.0}
        )

    if doc.page_count > 0:
        page = doc[0]
        blocks = page.get_text("dict").get("blocks", [])
        lines: list[dict[str, float | str]] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_text = _normalize_title_candidate(
                    "".join(span["text"] for span in line["spans"])
                )
                if not line_text:
                    continue
                max_font = max(
                    (span["size"] for span in line["spans"] if span["text"].strip()),
                    default=0,
                )
                y0 = min(
                    (span["bbox"][1] for span in line["spans"] if span["text"].strip()),
                    default=9999,
                )
                lines.append(
                    {
                        "text": line_text,
                        "source": "line",
                        "font_size": float(max_font),
                        "y0": float(y0),
                    }
                )

        lines.sort(key=lambda item: (float(item["y0"]), -float(item["font_size"])))
        candidates.extend(lines)

        if lines:
            top_font = max(float(item["font_size"]) for item in lines)
            large_lines = [
                item
                for item in lines
                if float(item["font_size"]) >= max(12.0, top_font - 1.5)
                and float(item["y0"]) <= 260
            ]
            large_lines.sort(key=lambda item: float(item["y0"]))
            cluster: list[dict[str, float | str]] = []
            previous_y0: float | None = None
            for item in large_lines:
                current_y0 = float(item["y0"])
                if previous_y0 is None or current_y0 - previous_y0 <= 40:
                    cluster.append(item)
                    previous_y0 = current_y0
                    continue
                break
            if cluster:
                candidates.append(
                    {
                        "text": " ".join(str(item["text"]) for item in cluster),
                        "source": "cluster",
                        "font_size": max(float(item["font_size"]) for item in cluster),
                        "y0": min(float(item["y0"]) for item in cluster),
                    }
                )

    filename_candidate = _filename_title_candidate(filepath)
    if filename_candidate:
        candidates.append(
            {"text": filename_candidate, "source": "filename", "font_size": 0.0, "y0": 9999.0}
        )

    return candidates


def _detect_best_title(text: str, doc: fitz.Document, filepath: str) -> str:
    candidates = _extract_title_candidates(doc, filepath)
    best_title = ""
    best_score = -1000.0

    for candidate in candidates:
        score = _score_title_candidate(
            str(candidate["text"]),
            source=str(candidate["source"]),
            font_size=float(candidate["font_size"]),
            y0=float(candidate["y0"]),
        )
        if score > best_score:
            best_title = _normalize_title_candidate(str(candidate["text"]))
            best_score = score

    if best_score > -1000.0:
        return best_title

    lines = text.strip().split("\n")
    for line in lines[:20]:
        stripped = _normalize_title_candidate(line)
        if stripped and not _looks_like_metadata_line(stripped):
            return stripped

    return _filename_title_candidate(filepath)


def _detect_title(text: str, doc: fitz.Document, filepath: str = "") -> str:
    # Try font-size鈥揵ased detection on the first page
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

        title = _detect_best_title(full_text, doc, filepath)
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
    if result.created_at is None:
        result.created_at = datetime.now(timezone.utc).isoformat()
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2, ensure_ascii=False))
    return filepath


def load_parsed_result(paper_id: str, metadata_dir: str) -> dict:
    filepath = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"论文解析结果不存在: {filepath}，请先上传并解析 PDF")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def update_parsed_title(paper_id: str, metadata_dir: str, title: str) -> dict:
    data = load_parsed_result(paper_id, metadata_dir)
    data["title"] = _normalize_title_candidate(title)

    filepath = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


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
                paper_id = fname.replace("_parsed.json", "")
                filepath = os.path.join(metadata_dir, fname)
                data = load_parsed_result(
                    paper_id, metadata_dir
                )
                created_at = data.get("created_at")
                if not created_at:
                    created_at = datetime.fromtimestamp(
                        os.path.getmtime(filepath), timezone.utc
                    ).isoformat()
                papers.append(
                    {
                        "paper_id": data.get("paper_id", ""),
                        "title": data.get("title", ""),
                        "abstract": data.get("abstract", "")[:200],
                        "created_at": created_at,
                        "source": data.get("source") or "upload",
                        "source_id": data.get("source_id"),
                    }
                )
            except Exception:
                continue
    return papers


# ==================== PDF Profile Generation ====================


def _detect_layout_type(doc: fitz.Document) -> str:
    """
    妫€娴嬬増寮忕被鍨嬶紙鍗曟爮 vs 鍙屾爮锛?

    Args:
        doc: PyMuPDF Document 瀵硅薄

    Returns:
        "single_column", "double_column", 鎴?"unknown"
    """
    if doc.page_count == 0:
        return "unknown"

    sample_pages = min(5, doc.page_count)
    left_blocks = 0
    right_blocks = 0

    for page_num in range(sample_pages):
        page = doc[page_num]
        page_width = page.rect.width
        blocks = page.get_text("dict").get("blocks", [])

        for block in blocks:
            if block.get("type") != 0:  # 鍙湅鏂囨湰鍧?
                continue
            bbox = block.get("bbox", [0, 0, 0, 0])
            x0 = bbox[0]

            if x0 < page_width * 0.4:
                left_blocks += 1
            elif x0 > page_width * 0.55:
                right_blocks += 1

    # 濡傛灉鍙充晶 block 鏁伴噺瓒呰繃鎬绘暟鐨?30%锛屽垽瀹氫负鍙屾爮
    total = left_blocks + right_blocks
    if total > 0 and right_blocks / total > 0.3:
        return "double_column"
    elif total > 0:
        return "single_column"
    else:
        return "unknown"


def _detect_tables_and_figures(doc: fitz.Document) -> tuple[bool, bool]:
    """
    妫€娴嬭〃鏍煎拰鍥剧墖

    Args:
        doc: PyMuPDF Document 瀵硅薄

    Returns:
        (has_tables, has_figures) 鍏冪粍
    """
    has_tables = False
    has_figures = False

    for page in doc:
        blocks = page.get_text("dict").get("blocks", [])
        for block in blocks:
            if block.get("type") == 1:  # 鍥剧墖鍧?
                has_figures = True
            elif block.get("type") == 0:  # 鏂囨湰鍧?
                # 绠€鍗曟娴嬶細濡傛灉鏂囨湰鍖呭惈澶氫釜杩炵画绌烘牸鎴栧埗琛ㄧ锛屽彲鑳芥槸琛ㄦ牸
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                # 妫€娴嬪涓繛缁┖鏍兼垨鍒惰〃绗︼紙琛ㄦ牸鐗瑰緛锛?
                if "  " in text or "\t" in text:
                    has_tables = True

            # 鎻愬墠閫€鍑轰紭鍖?
            if has_tables and has_figures:
                break
        if has_tables and has_figures:
            break

    return has_tables, has_figures


def _detect_reference_page(doc: fitz.Document) -> int | None:
    """
    妫€娴嬪弬鑰冩枃鐚捣濮嬮〉

    Args:
        doc: PyMuPDF Document 瀵硅薄

    Returns:
        鍙傝€冩枃鐚捣濮嬮〉鐮侊紙浠?1 寮€濮嬶級锛屽鏋滄湭鎵惧埌鍒欒繑鍥?None
    """
    for page_num in range(doc.page_count):
        page = doc[page_num]
        text = page.get_text()
        # 鍖归厤 "References", "REFERENCES", "Bibliography", "BIBLIOGRAPHY"
        if re.search(r'\bReferences?\b|\bBIBLIOGRAPHY\b', text, re.IGNORECASE):
            return page_num + 1  # 椤电爜浠?1 寮€濮?
    return None


def generate_pdf_profile(doc: fitz.Document, paper_id: str) -> PdfProfile:
    """
    鐢熸垚 PDF 绫诲瀷鍜岀増寮忚瘑鍒粨鏋溿€?

    Args:
        doc: PyMuPDF Document 瀵硅薄
        paper_id: 璁烘枃 ID

    Returns:
        PdfProfile 瀵硅薄

    Raises:
        ValueError: 濡傛灉鏄壂鎻忕増 PDF锛堟棤娉曟彁鍙栨枃鏈級
    """
    page_count = doc.page_count

    # 1. 缁熻鏂囨湰瀛楃鎬绘暟
    total_chars = 0
    for page in doc:
        text = page.get_text()
        total_chars += len(text.strip())

    # 2. 鍒ゆ柇鏄惁涓烘枃鏈瀷 PDF
    min_chars_threshold = page_count * 100
    is_text_pdf = total_chars >= min_chars_threshold

    if not is_text_pdf:
        logger.error(
            "PDF %s 为扫描版或图片型：总字符数 %d < 阈值 %d",
            paper_id,
            total_chars,
            min_chars_threshold,
        )
        raise ValueError("PDF 为扫描版或图片型，无法提取文本内容，当前版本不支持 OCR")

    # 3. 璁＄畻鏂囨湰瀵嗗害
    text_density = total_chars / page_count if page_count > 0 else 0.0

    # 4. 妫€娴嬬増寮忕被鍨?
    layout_type = _detect_layout_type(doc)

    # 5. 妫€娴嬭〃鏍煎拰鍥剧墖
    has_tables, has_figures = _detect_tables_and_figures(doc)

    # 6. 妫€娴嬪弬鑰冩枃鐚捣濮嬮〉
    reference_page_start = _detect_reference_page(doc)

    # 7. 鐢熸垚璀﹀憡
    warnings = []
    if text_density < 500:
        warnings.append("Text density is low; parsing quality may be affected")

    profile = PdfProfile(
        paper_id=paper_id,
        page_count=page_count,
        is_text_pdf=is_text_pdf,
        layout_type=layout_type,
        text_density=round(text_density, 2),
        has_tables=has_tables,
        has_figures=has_figures,
        reference_page_start=reference_page_start,
        warnings=warnings,
    )

    logger.info(
        "PDF profile generated: %s, pages=%d, layout=%s, density=%.2f, tables=%s, figures=%s",
        paper_id,
        page_count,
        layout_type,
        text_density,
        has_tables,
        has_figures,
    )

    return profile


# ==================== Structured Element Parsing ====================


def _sort_blocks_by_reading_order(
    blocks: list, page_width: float, layout_type: str
) -> list:
    """
    鎸夐槄璇婚『搴忓 blocks 鎺掑簭銆?

    Args:
        blocks: PyMuPDF blocks 鍒楄〃
        page_width: 椤甸潰瀹藉害
        layout_type: 鐗堝紡绫诲瀷 (single_column/double_column/unknown)

    Returns:
        鎺掑簭鍚庣殑 blocks 鍒楄〃
    """
    if layout_type == "double_column":
        # 鍒嗙宸﹀彸鏍?
        left_blocks = [b for b in blocks if b.get("bbox", [0])[0] < page_width / 2]
        right_blocks = [b for b in blocks if b.get("bbox", [0])[0] >= page_width / 2]

        # 姣忔爮鍐呴儴鎸?y0 鎺掑簭
        left_blocks.sort(key=lambda b: b.get("bbox", [0, 0])[1])
        right_blocks.sort(key=lambda b: b.get("bbox", [0, 0])[1])

        # 鍚堝苟锛氬乏鏍忓湪鍓嶏紝鍙虫爮鍦ㄥ悗
        return left_blocks + right_blocks
    else:
        # 鍗曟爮鎴栨湭鐭ワ細鐩存帴鎸?y0 鎺掑簭
        return sorted(blocks, key=lambda b: b.get("bbox", [0, 0])[1])


def _classify_block_type(block: dict, page_num: int, doc: fitz.Document) -> str:
    """
    璇嗗埆 block 绫诲瀷锛堝惎鍙戝紡锛夈€?

    Args:
        block: PyMuPDF block 瀛楀吀
        page_num: 椤电爜锛堜粠 0 寮€濮嬶級
        doc: PyMuPDF Document 瀵硅薄

    Returns:
        绫诲瀷瀛楃涓? "title" | "abstract" | "heading" | "paragraph" |
                    "table" | "figure_caption" | "equation" | "reference"
    """
    # 鍥剧墖 block
    if block.get("type") == 1:
        return "figure_caption"

    # 鎻愬彇鏂囨湰鍜屽瓧浣撲俊鎭?
    text = ""
    font_sizes = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            span_text = span.get("text", "")
            text += span_text
            if span_text.strip():
                font_sizes.append(span.get("size", 0))

    text = text.strip()
    if not text:
        return "paragraph"

    # 绗竴椤?+ 澶у瓧浣?-> 鍙兘鏄爣棰?
    if page_num == 0 and font_sizes:
        max_font = max(font_sizes)
        if max_font > 14:
            return "title"

    # 鐭枃鏈紙鍙兘鏄爣棰橈級- 灏忎簬 100 瀛楃涓斾笉鍖呭惈鍙ュ彿锛堟帓闄ゅ畬鏁村彞瀛愶級
    is_short = len(text) < 100 and text.count('.') <= 1

    # Abstract 鍏抽敭璇?
    if re.match(r"^\s*abstract\s*$", text, re.IGNORECASE):
        return "heading"

    # 绔犺妭鏍囬鍏抽敭璇嶏紙鏇村鏉剧殑鍖归厤锛屾敮鎸佺揣璐寸殑缂栧彿濡?"1Introduction"锛?
    heading_keywords = [
        "introduction",
        "related work",
        "background",
        "method",
        "methodology",
        "approach",
        "experiment",
        "results",
        "evaluation",
        "discussion",
        "conclusion",
        "references",
        "bibliography",
        "acknowledgment",
        "preliminaries",
        "overview",
        "motivation",
        "contributions",
        "analysis",
    ]
    text_lower = text.lower()

    # 妫€娴嬪悇绉嶇珷鑺傛爣棰樻牸寮?
    for kw in heading_keywords:
        # 鏍囧噯鏍煎紡: "1. Introduction" 鎴?"Introduction"
        if re.match(rf"^\s*(\d+[\.\)]\s*)?{kw}s?\s*$", text_lower):
            return "heading"

        # 绱ц创鏍煎紡: "1Introduction" (鏃犵┖鏍?
        if is_short and re.match(rf"^\s*\d+{kw}s?\s*$", text_lower):
            return "heading"

        # 瀛愮珷鑺傛牸寮? "1.1 Background" 鎴?"1.1.1 Details"
        if is_short and re.match(rf"^\s*\d+(\.\d+)*\s+{kw}", text_lower):
            return "heading"

    # 鍙傝€冩枃鐚唴瀹癸紙绠€鍖栵細鍖呭惈 "[1]" 鎴?"1." 寮€澶达級
    if re.match(r"^\s*[\[\(]?\d+[\]\)\.]\s+", text):
        return "reference"

    # 琛ㄦ牸锛堝惎鍙戝紡锛氬涓繛缁┖鏍兼垨鍒惰〃绗︼級
    if "  " in text or "\t" in text:
        return "table"

    # 鍏紡锛堝惎鍙戝紡锛氬寘鍚ぇ閲忔暟瀛︾鍙凤級
    math_symbols = ["∫", "∑", "∏", "√", "∂", "∇", "≈", "≤", "≥", "×", "÷"]
    if any(sym in text for sym in math_symbols):
        return "equation"

    # 榛樿涓烘钀?
    return "paragraph"


def parse_structured_elements(
    doc: fitz.Document, paper_id: str, layout_type: str = "unknown"
) -> list[DocumentElement]:
    """
    灏?PDF 瑙ｆ瀽涓虹粨鏋勫寲鍏冪礌鍒楄〃銆?

    Args:
        doc: PyMuPDF Document 瀵硅薄
        paper_id: 璁烘枃 ID
        layout_type: 鐗堝紡绫诲瀷 (single_column/double_column/unknown)

    Returns:
        DocumentElement 鍒楄〃锛屾寜闃呰椤哄簭鎺掑簭
    """
    logger.info(
        "Starting structured element parsing for %s with layout_type=%s",
        paper_id,
        layout_type,
    )

    elements = []
    order_index = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        page_width = page.rect.width
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])

        # 鎸夐槄璇婚『搴忔帓搴?
        sorted_blocks = _sort_blocks_by_reading_order(blocks, page_width, layout_type)

        # 缁熻鍏冪礌绫诲瀷鍒嗗竷锛堢敤浜庢棩蹇楋級
        type_counts = {}

        for block in sorted_blocks:
            # 璇嗗埆鍏冪礌绫诲瀷
            element_type = _classify_block_type(block, page_num, doc)

            # 鎻愬彇鏂囨湰
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")

            text = text.strip()

            # 杩囨护绌哄厓绱狅紙鍥剧墖闄ゅ锛?
            if not text and element_type != "figure_caption":
                continue

            # 鎻愬彇 bbox
            bbox = tuple(block.get("bbox", [0, 0, 0, 0]))

            # 鏋勫缓 DocumentElement
            element_id = f"{paper_id}_elem_{order_index:05d}"
            element = DocumentElement(
                element_id=element_id,
                paper_id=paper_id,
                type=element_type,
                text=text,
                page_number=page_num + 1,  # 椤电爜浠?1 寮€濮?
                bbox=bbox,
                section_path=None,  # 鍚庣画 Task 2.3 浼氬～鍏?
                order_index=order_index,
                metadata={},
            )

            elements.append(element)
            order_index += 1

            # 缁熻绫诲瀷
            type_counts[element_type] = type_counts.get(element_type, 0) + 1

        # 璁板綍姣忛〉鐨勭粺璁′俊鎭?
        if type_counts:
            logger.debug(
                "Page %d: %d blocks, types=%s",
                page_num + 1,
                len(sorted_blocks),
                type_counts,
            )

    logger.info(
        "Structured element parsing completed for %s: %d elements",
        paper_id,
        len(elements),
    )

    return elements

# ==================== Section Tree Building ====================


def _detect_heading_level(element: DocumentElement) -> int:
    """
    璇嗗埆鏍囬灞傜骇銆?

    Args:
        element: DocumentElement 瀵硅薄

    Returns:
        1, 2, 鎴?3锛堜竴绾с€佷簩绾с€佷笁绾ф爣棰橈級
    """
    text = element.text.strip()

    # 妫€娴嬬紪鍙锋ā寮?
    # 涓夌骇: 1.1.1, 2.1.2
    if re.match(r"^\d+\.\d+\.\d+", text):
        return 3

    # 浜岀骇: 1.1, 2.3
    if re.match(r"^\d+\.\d+", text):
        return 2

    # 涓€绾х紪鍙? 1., 2., I., II., III.
    if re.match(r"^(\d+\.?|[IVX]+\.)\s", text):
        return 1

    # 鍏抽敭璇嶅尮閰嶏紙涓€绾ф爣棰橈級
    main_keywords = [
        "abstract",
        "introduction",
        "related work",
        "background",
        "method",
        "methodology",
        "approach",
        "experiment",
        "experiments",
        "results",
        "evaluation",
        "discussion",
        "conclusion",
        "conclusions",
        "references",
        "bibliography",
        "acknowledgment",
        "acknowledgments",
    ]

    text_lower = text.lower()
    for kw in main_keywords:
        if re.match(rf"^\s*(\d+[\.\)]\s*)?{kw}s?\s*$", text_lower):
            return 1

    # 榛樿浜岀骇鏍囬锛堝鏋滄槸 heading 浣嗕笉鍖归厤涓婅堪瑙勫垯锛?
    return 2


def build_section_tree(elements: list[DocumentElement]) -> list[DocumentElement]:
    """
    鏋勫缓绔犺妭灞傛缁撴瀯锛屼负姣忎釜鍏冪礌濉厖 section_path銆?

    Args:
        elements: 缁撴瀯鍖栧厓绱犲垪琛紙鏉ヨ嚜 parse_structured_elements锛?

    Returns:
        鏇存柊浜?section_path 鐨勫厓绱犲垪琛紙鍘熷湴淇敼 + 杩斿洖锛?
    """
    logger.info("Building section tree for %d elements", len(elements))

    # 褰撳墠绔犺妭璺緞鏍?
    current_path: list[str] = []

    # 鏄惁杩涘叆鍙傝€冩枃鐚儴鍒?
    in_references = False

    # 缁熻璇嗗埆鐨勭珷鑺傛暟閲?
    section_count = 0
    level_counts = {1: 0, 2: 0, 3: 0}

    for element in elements:
        # 妫€娴嬫槸鍚︿负 References 鏍囬
        if element.type in ["heading", "title"]:
            text_lower = element.text.strip().lower()
            # 鍖归厤 "References", "REFERENCES", "Bibliography"
            if re.match(r"^\s*(\d+[\.\)]\s*)?references?\s*$", text_lower) or re.match(
                r"^\s*(\d+[\.\)]\s*)?bibliography\s*$", text_lower
            ):
                in_references = True
                logger.debug(
                    "Detected References section at element %s", element.element_id
                )

        # 鏍囪 References 涔嬪悗鐨勫唴瀹?
        if in_references:
            element.metadata["in_references"] = True

        # 澶勭悊鏍囬鍏冪礌
        if element.type in ["heading", "title"]:
            # 璇嗗埆鏍囬灞傜骇
            level = _detect_heading_level(element)
            level_counts[level] = level_counts.get(level, 0) + 1

            # 鏇存柊绔犺妭璺緞鏍?
            if level == 1:
                current_path = [element.text.strip()]
                section_count += 1
            elif level == 2:
                if len(current_path) >= 1:
                    current_path = [current_path[0], element.text.strip()]
                else:
                    # 杈圭晫鎯呭喌锛氱涓€涓爣棰樺氨鏄簩绾ф爣棰?
                    current_path = [element.text.strip()]
                section_count += 1
            elif level == 3:
                if len(current_path) >= 2:
                    current_path = current_path[:2] + [element.text.strip()]
                elif len(current_path) == 1:
                    current_path.append(element.text.strip())
                else:
                    # 杈圭晫鎯呭喌锛氱涓€涓爣棰樺氨鏄笁绾ф爣棰?
                    current_path = [element.text.strip()]
                section_count += 1

            # 璁剧疆璇ユ爣棰樺厓绱犵殑 section_path
            element.section_path = "/".join(current_path)

            logger.debug(
                "Section: %s (level %d, element %s)",
                element.section_path,
                level,
                element.element_id,
            )
        else:
            # 闈炴爣棰樺厓绱狅細缁ф壙褰撳墠绔犺妭璺緞
            if current_path:
                element.section_path = "/".join(current_path)
            else:
                # 杈圭晫鎯呭喌锛氬湪绗竴涓珷鑺傛爣棰樹箣鍓嶇殑鍐呭锛堝鏍囬銆佹憳瑕侊級
                element.section_path = None

    logger.info(
        "Built section tree: %d sections found (L1=%d, L2=%d, L3=%d)",
        section_count,
        level_counts.get(1, 0),
        level_counts.get(2, 0),
        level_counts.get(3, 0),
    )

    return elements
