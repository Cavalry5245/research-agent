"""
父文档构建模块。

从结构化元素构建父文档，用于 Parent-Child RAG 架构。
"""

import logging
from collections import defaultdict

from app.schemas import DocumentElement, ParentDocument

logger = logging.getLogger(__name__)


def build_parent_documents(
    elements: list[DocumentElement],
    paper_id: str,
    paper_title: str,
) -> list[ParentDocument]:
    """
    从结构化元素构建父文档。

    父文档边界规则：
    1. Abstract: 独立父文档
    2. 主章节: 一级标题开始的内容为一个父文档
    3. 二级章节: 如果内容超过 2000 字符，独立为父文档
    4. 表格: 独立父文档（element_type == "table"）
    5. 图注: 归属到所在章节父文档
    6. References: 跳过 metadata["in_references"] == True 的元素

    Args:
        elements: 结构化元素列表（已填充 section_path）
        paper_id: 论文 ID
        paper_title: 论文标题

    Returns:
        父文档列表
    """
    if not elements:
        logger.warning("build_parent_documents: empty elements list for paper %s", paper_id)
        return []

    # 过滤掉 References 中的元素
    filtered_elements = [
        elem for elem in elements
        if not elem.metadata.get("in_references", False)
    ]

    if not filtered_elements:
        logger.warning("build_parent_documents: all elements filtered out for paper %s", paper_id)
        return []

    logger.info(
        "build_parent_documents: paper=%s, total_elements=%d, after_filter=%d",
        paper_id,
        len(elements),
        len(filtered_elements),
    )

    parents: list[ParentDocument] = []
    seq = 1

    # 1. Abstract 独立父文档
    abstract_elements = [elem for elem in filtered_elements if elem.type == "abstract"]
    if abstract_elements:
        parent = _build_single_parent(
            paper_id=paper_id,
            paper_title=paper_title,
            parent_id=f"{paper_id}_parent_{seq:04d}",
            section_path="Abstract",
            element_type="abstract",
            elements=abstract_elements,
        )
        parents.append(parent)
        seq += 1
        logger.debug("Created abstract parent: %s", parent.parent_id)

    # 2. 表格独立父文档
    table_elements = [elem for elem in filtered_elements if elem.type == "table"]
    for table_elem in table_elements:
        parent = _build_single_parent(
            paper_id=paper_id,
            paper_title=paper_title,
            parent_id=f"{paper_id}_parent_{seq:04d}",
            section_path=table_elem.section_path or "Unknown",
            element_type="table",
            elements=[table_elem],
        )
        parents.append(parent)
        seq += 1
        logger.debug("Created table parent: %s", parent.parent_id)

    # 3. 主章节和二级章节分组
    # 排除已处理的 abstract 和 table
    processed_ids = {elem.element_id for elem in abstract_elements + table_elements}
    section_elements = [
        elem for elem in filtered_elements
        if elem.element_id not in processed_ids
    ]

    # 按 section_path 分组
    section_groups: dict[str, list[DocumentElement]] = defaultdict(list)
    for elem in section_elements:
        path = elem.section_path or "Unknown"
        section_groups[path].append(elem)

    # 按照元素出现顺序排序 section_path（保持原始阅读顺序）
    section_paths_ordered = []
    seen_paths = set()
    for elem in section_elements:
        path = elem.section_path or "Unknown"
        if path not in seen_paths:
            section_paths_ordered.append(path)
            seen_paths.add(path)

    # 构建章节父文档
    for section_path in section_paths_ordered:
        group = section_groups[section_path]
        if not group:
            continue

        # 计算该组的总字符数
        total_chars = sum(len(elem.text) for elem in group)

        # 判断是否为二级章节（包含 "/"）
        is_subsection = "/" in section_path
        depth = section_path.count("/")

        # 规则：
        # - 一级章节（无 "/"）：总是独立父文档
        # - 二级章节（1 个 "/"）：如果超过 2000 字符，独立父文档；否则合并到一级
        # - 三级及以上：合并到上级
        if depth == 0:
            # 一级章节，独立父文档
            parent = _build_single_parent(
                paper_id=paper_id,
                paper_title=paper_title,
                parent_id=f"{paper_id}_parent_{seq:04d}",
                section_path=section_path,
                element_type="section",
                elements=group,
            )
            parents.append(parent)
            seq += 1
            logger.debug("Created L1 section parent: %s (chars=%d)", parent.parent_id, total_chars)

        elif depth == 1 and total_chars > 2000:
            # 二级章节且超过 2000 字符，独立父文档
            parent = _build_single_parent(
                paper_id=paper_id,
                paper_title=paper_title,
                parent_id=f"{paper_id}_parent_{seq:04d}",
                section_path=section_path,
                element_type="section",
                elements=group,
            )
            parents.append(parent)
            seq += 1
            logger.debug("Created L2 section parent: %s (chars=%d)", parent.parent_id, total_chars)

        else:
            # 二级章节不足 2000 字符，或三级以上，合并到父章节
            # 找到父章节路径（去掉最后一级）
            parent_path_parts = section_path.rsplit("/", 1)
            if len(parent_path_parts) > 1:
                parent_section_path = parent_path_parts[0]
            else:
                parent_section_path = section_path  # 已是顶级，保持原样

            # 尝试找到已存在的父章节父文档
            existing_parent = next(
                (p for p in parents if p.section_path == parent_section_path and p.element_type == "section"),
                None
            )

            if existing_parent:
                # 合并到已存在的父文档
                _merge_elements_to_parent(existing_parent, group)
                logger.debug(
                    "Merged subsection %s into existing parent %s (added %d chars)",
                    section_path,
                    existing_parent.parent_id,
                    total_chars,
                )
            else:
                # 如果父章节父文档不存在（可能父章节元素被过滤），创建新的 mixed 类型父文档
                parent = _build_single_parent(
                    paper_id=paper_id,
                    paper_title=paper_title,
                    parent_id=f"{paper_id}_parent_{seq:04d}",
                    section_path=section_path,
                    element_type="mixed",
                    elements=group,
                )
                parents.append(parent)
                seq += 1
                logger.debug(
                    "Created mixed subsection parent: %s (chars=%d, no parent found)",
                    parent.parent_id,
                    total_chars,
                )

    logger.info(
        "build_parent_documents: paper=%s, created %d parent documents",
        paper_id,
        len(parents),
    )

    return parents


def _build_single_parent(
    paper_id: str,
    paper_title: str,
    parent_id: str,
    section_path: str,
    element_type: str,
    elements: list[DocumentElement],
) -> ParentDocument:
    """
    从元素列表构建单个父文档。

    Args:
        paper_id: 论文 ID
        paper_title: 论文标题
        parent_id: 父文档 ID
        section_path: 章节路径
        element_type: 父文档类型
        elements: 元素列表

    Returns:
        父文档对象
    """
    # 聚合内容
    content_parts = [elem.text for elem in elements]
    content = "\n\n".join(content_parts)

    # 收集 element_ids
    element_ids = [elem.element_id for elem in elements]

    # 计算 page_range
    page_numbers = [elem.page_number for elem in elements if elem.page_number is not None]
    if page_numbers:
        min_page = min(page_numbers)
        max_page = max(page_numbers)
        if min_page == max_page:
            page_range = str(min_page)
        else:
            page_range = f"{min_page}-{max_page}"
    else:
        page_range = None

    # 收集 bbox_refs
    bbox_refs: list[tuple[int, tuple[float, float, float, float]]] = []
    for elem in elements:
        if elem.bbox is not None and elem.page_number is not None:
            bbox_refs.append((elem.page_number, elem.bbox))

    parent = ParentDocument(
        parent_id=parent_id,
        paper_id=paper_id,
        title=paper_title,
        section_path=section_path,
        content=content,
        page_range=page_range,
        element_type=element_type,  # type: ignore
        element_ids=element_ids,
        bbox_refs=bbox_refs,
    )

    return parent


def _merge_elements_to_parent(
    parent: ParentDocument,
    elements: list[DocumentElement],
) -> None:
    """
    将元素合并到已存在的父文档中（就地修改）。

    Args:
        parent: 已存在的父文档
        elements: 要合并的元素列表
    """
    # 追加内容
    new_content_parts = [elem.text for elem in elements]
    new_content = "\n\n".join(new_content_parts)
    parent.content = parent.content + "\n\n" + new_content

    # 追加 element_ids
    parent.element_ids.extend([elem.element_id for elem in elements])

    # 更新 page_range
    page_numbers = [elem.page_number for elem in elements if elem.page_number is not None]
    if page_numbers:
        new_min = min(page_numbers)
        new_max = max(page_numbers)

        # 解析当前 page_range
        if parent.page_range:
            if "-" in parent.page_range:
                current_min, current_max = map(int, parent.page_range.split("-"))
            else:
                current_min = current_max = int(parent.page_range)

            # 合并范围
            merged_min = min(current_min, new_min)
            merged_max = max(current_max, new_max)

            if merged_min == merged_max:
                parent.page_range = str(merged_min)
            else:
                parent.page_range = f"{merged_min}-{merged_max}"
        else:
            # 原父文档没有 page_range，设置新的
            if new_min == new_max:
                parent.page_range = str(new_min)
            else:
                parent.page_range = f"{new_min}-{new_max}"

    # 追加 bbox_refs
    for elem in elements:
        if elem.bbox is not None and elem.page_number is not None:
            parent.bbox_refs.append((elem.page_number, elem.bbox))


def chunk_parent_documents(
    parents: list[ParentDocument],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    min_chunk_chars: int = 20,
) -> list["Chunk"]:
    """
    对父文档执行滑动窗口切分，生成子块。

    每个父文档独立切分，子块不跨父文档边界。

    Args:
        parents: 父文档列表
        chunk_size: chunk 大小（字符数）
        chunk_overlap: 重叠大小（字符数）
        min_chunk_chars: 最小 chunk 字符数

    Returns:
        子块列表（Chunk 对象），每个子块包含 parent_id 和所有新增字段
    """
    from app.schemas import Chunk
    from app.services.chunker import _sliding_window

    if not parents:
        logger.warning("chunk_parent_documents: empty parents list")
        return []

    logger.info(
        "chunk_parent_documents: processing %d parent documents with chunk_size=%d, overlap=%d",
        len(parents),
        chunk_size,
        chunk_overlap,
    )

    chunks: list[Chunk] = []
    chunk_seq = 1

    for parent in parents:
        # 获取父文档内容
        content = parent.content.strip()
        if not content or len(content) < min_chunk_chars:
            logger.debug(
                "Skipping parent %s: content too short (%d chars)",
                parent.parent_id,
                len(content),
            )
            continue

        # 对父文档执行滑动窗口切分
        text_parts = _sliding_window(content, chunk_size, chunk_overlap)

        # 如果父文档很短，至少生成一个子块
        if not text_parts and len(content) >= min_chunk_chars:
            text_parts = [(0, len(content), content)]

        # 为每个切分后的文本片段创建 Chunk
        for chunk_start, chunk_end, chunk_content in text_parts:
            if len(chunk_content) < min_chunk_chars:
                continue

            # 生成 chunk_id
            chunk_id = f"{parent.paper_id}_chunk_{chunk_seq:04d}"
            chunk_seq += 1

            # 提取 section 名称（从 section_path 提取最后一级）
            if parent.section_path and "/" in parent.section_path:
                section = parent.section_path.rsplit("/", 1)[-1]
            else:
                section = parent.section_path or "Unknown"

            # 构建 context_header
            context_header = (
                f"{parent.title} | "
                f"{parent.section_path or 'Unknown'} | "
                f"p.{parent.page_range or '?'}"
            )

            # 构建 content_for_embedding
            content_for_embedding = f"{context_header}\n\n{chunk_content}"

            # 提取起始页码
            page_number = None
            if parent.page_range:
                try:
                    if "-" in parent.page_range:
                        page_number = int(parent.page_range.split("-")[0])
                    else:
                        page_number = int(parent.page_range)
                except (ValueError, IndexError):
                    logger.warning(
                        "Failed to parse page_range '%s' for parent %s",
                        parent.page_range,
                        parent.parent_id,
                    )

            # 创建 Chunk 对象
            chunk = Chunk(
                chunk_id=chunk_id,
                paper_id=parent.paper_id,
                title=parent.title,
                section=section,
                content=chunk_content,
                page_number=page_number,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                # 新增字段
                parent_id=parent.parent_id,
                section_path=parent.section_path,
                page_range=parent.page_range,
                element_type=parent.element_type,
                content_for_embedding=content_for_embedding,
                context_header=context_header,
            )

            chunks.append(chunk)

        logger.debug(
            "Parent %s: generated %d chunks from %d chars",
            parent.parent_id,
            len(text_parts),
            len(content),
        )

    logger.info(
        "chunk_parent_documents: generated %d chunks from %d parents",
        len(chunks),
        len(parents),
    )

    return chunks
