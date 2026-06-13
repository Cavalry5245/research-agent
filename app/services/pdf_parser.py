import json
import logging
import os
import re
from datetime import date

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


# ==================== PDF Profile Generation ====================


def _detect_layout_type(doc: fitz.Document) -> str:
    """
    检测版式类型（单栏 vs 双栏）

    Args:
        doc: PyMuPDF Document 对象

    Returns:
        "single_column", "double_column", 或 "unknown"
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
            if block.get("type") != 0:  # 只看文本块
                continue
            bbox = block.get("bbox", [0, 0, 0, 0])
            x0 = bbox[0]

            if x0 < page_width * 0.4:
                left_blocks += 1
            elif x0 > page_width * 0.55:
                right_blocks += 1

    # 如果右侧 block 数量超过总数的 30%，判定为双栏
    total = left_blocks + right_blocks
    if total > 0 and right_blocks / total > 0.3:
        return "double_column"
    elif total > 0:
        return "single_column"
    else:
        return "unknown"


def _detect_tables_and_figures(doc: fitz.Document) -> tuple[bool, bool]:
    """
    检测表格和图片

    Args:
        doc: PyMuPDF Document 对象

    Returns:
        (has_tables, has_figures) 元组
    """
    has_tables = False
    has_figures = False

    for page in doc:
        blocks = page.get_text("dict").get("blocks", [])
        for block in blocks:
            if block.get("type") == 1:  # 图片块
                has_figures = True
            elif block.get("type") == 0:  # 文本块
                # 简单检测：如果文本包含多个连续空格或制表符，可能是表格
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                # 检测多个连续空格或制表符（表格特征）
                if "  " in text or "\t" in text:
                    has_tables = True

            # 提前退出优化
            if has_tables and has_figures:
                break
        if has_tables and has_figures:
            break

    return has_tables, has_figures


def _detect_reference_page(doc: fitz.Document) -> int | None:
    """
    检测参考文献起始页

    Args:
        doc: PyMuPDF Document 对象

    Returns:
        参考文献起始页码（从 1 开始），如果未找到则返回 None
    """
    for page_num in range(doc.page_count):
        page = doc[page_num]
        text = page.get_text()
        # 匹配 "References", "REFERENCES", "Bibliography", "BIBLIOGRAPHY"
        if re.search(r'\bReferences?\b|\bBIBLIOGRAPHY\b', text, re.IGNORECASE):
            return page_num + 1  # 页码从 1 开始
    return None


def generate_pdf_profile(doc: fitz.Document, paper_id: str) -> PdfProfile:
    """
    生成 PDF 类型和版式识别结果。

    Args:
        doc: PyMuPDF Document 对象
        paper_id: 论文 ID

    Returns:
        PdfProfile 对象

    Raises:
        ValueError: 如果是扫描版 PDF（无法提取文本）
    """
    page_count = doc.page_count

    # 1. 统计文本字符总数
    total_chars = 0
    for page in doc:
        text = page.get_text()
        total_chars += len(text.strip())

    # 2. 判断是否为文本型 PDF
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

    # 3. 计算文本密度
    text_density = total_chars / page_count if page_count > 0 else 0.0

    # 4. 检测版式类型
    layout_type = _detect_layout_type(doc)

    # 5. 检测表格和图片
    has_tables, has_figures = _detect_tables_and_figures(doc)

    # 6. 检测参考文献起始页
    reference_page_start = _detect_reference_page(doc)

    # 7. 生成警告
    warnings = []
    if text_density < 500:
        warnings.append("文本密度较低，可能影响解析质量")

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
    按阅读顺序对 blocks 排序。

    Args:
        blocks: PyMuPDF blocks 列表
        page_width: 页面宽度
        layout_type: 版式类型 (single_column/double_column/unknown)

    Returns:
        排序后的 blocks 列表
    """
    if layout_type == "double_column":
        # 分离左右栏
        left_blocks = [b for b in blocks if b.get("bbox", [0])[0] < page_width / 2]
        right_blocks = [b for b in blocks if b.get("bbox", [0])[0] >= page_width / 2]

        # 每栏内部按 y0 排序
        left_blocks.sort(key=lambda b: b.get("bbox", [0, 0])[1])
        right_blocks.sort(key=lambda b: b.get("bbox", [0, 0])[1])

        # 合并：左栏在前，右栏在后
        return left_blocks + right_blocks
    else:
        # 单栏或未知：直接按 y0 排序
        return sorted(blocks, key=lambda b: b.get("bbox", [0, 0])[1])


def _classify_block_type(block: dict, page_num: int, doc: fitz.Document) -> str:
    """
    识别 block 类型（启发式）。

    Args:
        block: PyMuPDF block 字典
        page_num: 页码（从 0 开始）
        doc: PyMuPDF Document 对象

    Returns:
        类型字符串: "title" | "abstract" | "heading" | "paragraph" |
                    "table" | "figure_caption" | "equation" | "reference"
    """
    # 图片 block
    if block.get("type") == 1:
        return "figure_caption"

    # 提取文本和字体信息
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

    # 第一页 + 大字体 -> 可能是标题
    if page_num == 0 and font_sizes:
        max_font = max(font_sizes)
        if max_font > 14:
            return "title"

    # 短文本（可能是标题）- 小于 100 字符且不包含句号（排除完整句子）
    is_short = len(text) < 100 and text.count('.') <= 1

    # Abstract 关键词
    if re.match(r"^\s*abstract\s*$", text, re.IGNORECASE):
        return "heading"

    # 章节标题关键词（更宽松的匹配，支持紧贴的编号如 "1Introduction"）
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

    # 检测各种章节标题格式
    for kw in heading_keywords:
        # 标准格式: "1. Introduction" 或 "Introduction"
        if re.match(rf"^\s*(\d+[\.\)]\s*)?{kw}s?\s*$", text_lower):
            return "heading"

        # 紧贴格式: "1Introduction" (无空格)
        if is_short and re.match(rf"^\s*\d+{kw}s?\s*$", text_lower):
            return "heading"

        # 子章节格式: "1.1 Background" 或 "1.1.1 Details"
        if is_short and re.match(rf"^\s*\d+(\.\d+)*\s+{kw}", text_lower):
            return "heading"

    # 参考文献内容（简化：包含 "[1]" 或 "1." 开头）
    if re.match(r"^\s*[\[\(]?\d+[\]\)\.]\s+", text):
        return "reference"

    # 表格（启发式：多个连续空格或制表符）
    if "  " in text or "\t" in text:
        return "table"

    # 公式（启发式：包含大量数学符号）
    math_symbols = ["∫", "∑", "∏", "√", "∂", "∇", "≈", "≤", "≥", "×", "÷"]
    if any(sym in text for sym in math_symbols):
        return "equation"

    # 默认为段落
    return "paragraph"


def parse_structured_elements(
    doc: fitz.Document, paper_id: str, layout_type: str = "unknown"
) -> list[DocumentElement]:
    """
    将 PDF 解析为结构化元素列表。

    Args:
        doc: PyMuPDF Document 对象
        paper_id: 论文 ID
        layout_type: 版式类型 (single_column/double_column/unknown)

    Returns:
        DocumentElement 列表，按阅读顺序排序
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

        # 按阅读顺序排序
        sorted_blocks = _sort_blocks_by_reading_order(blocks, page_width, layout_type)

        # 统计元素类型分布（用于日志）
        type_counts = {}

        for block in sorted_blocks:
            # 识别元素类型
            element_type = _classify_block_type(block, page_num, doc)

            # 提取文本
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")

            text = text.strip()

            # 过滤空元素（图片除外）
            if not text and element_type != "figure_caption":
                continue

            # 提取 bbox
            bbox = tuple(block.get("bbox", [0, 0, 0, 0]))

            # 构建 DocumentElement
            element_id = f"{paper_id}_elem_{order_index:05d}"
            element = DocumentElement(
                element_id=element_id,
                paper_id=paper_id,
                type=element_type,
                text=text,
                page_number=page_num + 1,  # 页码从 1 开始
                bbox=bbox,
                section_path=None,  # 后续 Task 2.3 会填充
                order_index=order_index,
                metadata={},
            )

            elements.append(element)
            order_index += 1

            # 统计类型
            type_counts[element_type] = type_counts.get(element_type, 0) + 1

        # 记录每页的统计信息
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
    识别标题层级。

    Args:
        element: DocumentElement 对象

    Returns:
        1, 2, 或 3（一级、二级、三级标题）
    """
    text = element.text.strip()

    # 检测编号模式
    # 三级: 1.1.1, 2.1.2
    if re.match(r"^\d+\.\d+\.\d+", text):
        return 3

    # 二级: 1.1, 2.3
    if re.match(r"^\d+\.\d+", text):
        return 2

    # 一级编号: 1., 2., I., II., III.
    if re.match(r"^(\d+\.?|[IVX]+\.)\s", text):
        return 1

    # 关键词匹配（一级标题）
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

    # 默认二级标题（如果是 heading 但不匹配上述规则）
    return 2


def build_section_tree(elements: list[DocumentElement]) -> list[DocumentElement]:
    """
    构建章节层次结构，为每个元素填充 section_path。

    Args:
        elements: 结构化元素列表（来自 parse_structured_elements）

    Returns:
        更新了 section_path 的元素列表（原地修改 + 返回）
    """
    logger.info("Building section tree for %d elements", len(elements))

    # 当前章节路径栈
    current_path: list[str] = []

    # 是否进入参考文献部分
    in_references = False

    # 统计识别的章节数量
    section_count = 0
    level_counts = {1: 0, 2: 0, 3: 0}

    for element in elements:
        # 检测是否为 References 标题
        if element.type in ["heading", "title"]:
            text_lower = element.text.strip().lower()
            # 匹配 "References", "REFERENCES", "Bibliography"
            if re.match(r"^\s*(\d+[\.\)]\s*)?references?\s*$", text_lower) or re.match(
                r"^\s*(\d+[\.\)]\s*)?bibliography\s*$", text_lower
            ):
                in_references = True
                logger.debug(
                    "Detected References section at element %s", element.element_id
                )

        # 标记 References 之后的内容
        if in_references:
            element.metadata["in_references"] = True

        # 处理标题元素
        if element.type in ["heading", "title"]:
            # 识别标题层级
            level = _detect_heading_level(element)
            level_counts[level] = level_counts.get(level, 0) + 1

            # 更新章节路径栈
            if level == 1:
                current_path = [element.text.strip()]
                section_count += 1
            elif level == 2:
                if len(current_path) >= 1:
                    current_path = [current_path[0], element.text.strip()]
                else:
                    # 边界情况：第一个标题就是二级标题
                    current_path = [element.text.strip()]
                section_count += 1
            elif level == 3:
                if len(current_path) >= 2:
                    current_path = current_path[:2] + [element.text.strip()]
                elif len(current_path) == 1:
                    current_path.append(element.text.strip())
                else:
                    # 边界情况：第一个标题就是三级标题
                    current_path = [element.text.strip()]
                section_count += 1

            # 设置该标题元素的 section_path
            element.section_path = "/".join(current_path)

            logger.debug(
                "Section: %s (level %d, element %s)",
                element.section_path,
                level,
                element.element_id,
            )
        else:
            # 非标题元素：继承当前章节路径
            if current_path:
                element.section_path = "/".join(current_path)
            else:
                # 边界情况：在第一个章节标题之前的内容（如标题、摘要）
                element.section_path = None

    logger.info(
        "Built section tree: %d sections found (L1=%d, L2=%d, L3=%d)",
        section_count,
        level_counts.get(1, 0),
        level_counts.get(2, 0),
        level_counts.get(3, 0),
    )

    return elements
