"""
PaperCandidate Normalizer and Deduplication

将 Semantic Scholar、arXiv、Zotero 的原始数据归一化为统一 PaperCandidate，
并实现基于 DOI/arXiv ID/标题的去重逻辑。
"""

import re
from typing import Any

from app.research_pipeline.schemas import PaperCandidate


def normalize_semantic_scholar_paper(raw: dict[str, Any]) -> PaperCandidate:
    """
    归一化 Semantic Scholar 论文数据。

    Args:
        raw: Semantic Scholar API 返回的原始论文数据

    Returns:
        归一化后的 PaperCandidate
    """
    paper_id = raw.get("paperId", "")
    title = raw.get("title", "")

    # 提取作者
    authors = []
    for author in raw.get("authors", []):
        if isinstance(author, dict) and "name" in author:
            authors.append(author["name"])

    # 提取外部 ID
    external_ids = raw.get("externalIds", {}) or {}
    doi = external_ids.get("DOI")
    arxiv_id = external_ids.get("ArXiv")

    # 提取 PDF URL
    pdf_url = None
    open_access_pdf = raw.get("openAccessPdf")
    if isinstance(open_access_pdf, dict):
        pdf_url = open_access_pdf.get("url")

    # 提取年份
    year = raw.get("year")

    # 提取 venue
    venue = raw.get("venue")

    # 提取摘要
    abstract = raw.get("abstract")

    # 提取引用数
    citation_count = raw.get("citationCount")

    # 提取 URL
    url = raw.get("url")

    return PaperCandidate(
        paper_id=paper_id,
        source="semantic_scholar",
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract=abstract,
        doi=doi,
        arxiv_id=arxiv_id,
        semantic_scholar_id=paper_id,
        zotero_item_id=None,
        url=url,
        pdf_url=pdf_url,
        local_pdf_path=None,
        citation_count=citation_count,
    )


def normalize_arxiv_paper(raw: dict[str, Any]) -> PaperCandidate:
    """
    归一化 arXiv 论文数据。

    Args:
        raw: arXiv API 返回的原始论文数据

    Returns:
        归一化后的 PaperCandidate
    """
    arxiv_id = raw.get("arxiv_id") or _extract_arxiv_id(raw.get("id", ""))
    title = raw.get("title", "")

    # 提取作者
    authors = []
    for author in raw.get("authors", []):
        if isinstance(author, dict) and "name" in author:
            authors.append(author["name"])
        elif isinstance(author, str):
            authors.append(author)

    # 提取年份（从 published 字段）
    year = None
    published = raw.get("published")
    if published:
        # 格式: "2017-06-12T17:57:34Z"
        match = re.match(r"(\d{4})", published)
        if match:
            year = int(match.group(1))

    # 提取摘要
    abstract = raw.get("summary") or raw.get("abstract")

    # 提取 DOI
    doi = raw.get("doi")

    # 提取 URL
    url = raw.get("id")

    # 提取 PDF URL
    pdf_url = raw.get("pdf_url")

    return PaperCandidate(
        paper_id=arxiv_id,
        source="arxiv",
        title=title,
        authors=authors,
        year=year,
        venue=None,  # arXiv 没有 venue
        abstract=abstract,
        doi=doi,
        arxiv_id=arxiv_id,
        semantic_scholar_id=None,
        zotero_item_id=None,
        url=url,
        pdf_url=pdf_url,
        local_pdf_path=None,
        citation_count=None,
    )


def _extract_arxiv_id(value: str) -> str:
    """
    Extract a stable arXiv identifier from an arXiv URL or raw id.

    Examples:
    - http://arxiv.org/abs/2401.12345v2 -> 2401.12345
    - 2401.12345v2 -> 2401.12345
    """
    if not value:
        return ""

    raw_id = value.rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", raw_id)


def normalize_zotero_paper(raw: dict[str, Any]) -> PaperCandidate:
    """
    归一化 Zotero 论文数据。

    Args:
        raw: Zotero API 返回的原始论文数据

    Returns:
        归一化后的 PaperCandidate
    """
    item_key = raw.get("key", "")
    data = raw.get("data", {})

    title = data.get("title", "")

    # 提取作者
    authors = []
    for creator in data.get("creators", []):
        if isinstance(creator, dict) and creator.get("creatorType") == "author":
            first_name = creator.get("firstName", "")
            last_name = creator.get("lastName", "")
            if first_name and last_name:
                authors.append(f"{first_name} {last_name}")
            elif last_name:
                authors.append(last_name)
            elif first_name:
                authors.append(first_name)

    # 提取年份
    year = None
    date_str = data.get("date", "")
    if date_str:
        # 尝试多种格式
        match = re.search(r"(\d{4})", date_str)
        if match:
            year = int(match.group(1))

    # 提取 venue
    venue = data.get("publicationTitle")

    # 提取摘要
    abstract = data.get("abstractNote")

    # 提取 DOI
    doi = data.get("DOI")

    # 提取 arXiv ID（从 extra 字段）
    arxiv_id = None
    extra = data.get("extra", "")
    if extra:
        # 格式: "arXiv:1706.03762"
        match = re.search(r"arXiv:(\S+)", extra)
        if match:
            arxiv_id = match.group(1)

    # 提取 URL
    url = data.get("url")

    # 提取本地 PDF 路径
    local_pdf_path = None
    links = raw.get("links", {})
    if isinstance(links, dict):
        attachment = links.get("attachment")
        if isinstance(attachment, dict):
            local_pdf_path = attachment.get("path")

    return PaperCandidate(
        paper_id=item_key,
        source="zotero",
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract=abstract,
        doi=doi,
        arxiv_id=arxiv_id,
        semantic_scholar_id=None,
        zotero_item_id=item_key,
        url=url,
        pdf_url=None,
        local_pdf_path=local_pdf_path,
        citation_count=None,
    )


def _normalize_title(title: str) -> str:
    """
    标准化标题用于去重。

    - 转小写
    - 移除标点符号
    - 合并多余空格
    - 去除首尾空格
    """
    # 转小写
    normalized = title.lower()
    # 移除标点符号
    normalized = re.sub(r"[^\w\s]", "", normalized)
    # 合并多余空格
    normalized = re.sub(r"\s+", " ", normalized)
    # 去除首尾空格
    normalized = normalized.strip()
    return normalized


def deduplicate_candidates(candidates: list[PaperCandidate]) -> list[PaperCandidate]:
    """
    对候选论文列表进行去重。

    去重策略（优先级从高到低）：
    1. DOI
    2. arXiv ID
    3. Semantic Scholar ID
    4. 标准化标题

    当发现重复时：
    - 优先保留 source="zotero" 的 seed paper
    - 合并其他来源的元数据（IDs, citation_count, pdf_url 等）

    Args:
        candidates: 候选论文列表

    Returns:
        去重后的候选论文列表
    """
    if not candidates:
        return []

    # 构建去重索引
    doi_map: dict[str, list[PaperCandidate]] = {}
    arxiv_map: dict[str, list[PaperCandidate]] = {}
    ss_map: dict[str, list[PaperCandidate]] = {}
    title_map: dict[str, list[PaperCandidate]] = {}

    # 第一轮：按各种 key 分组
    for candidate in candidates:
        if candidate.doi:
            doi_key = candidate.doi.lower().strip()
            doi_map.setdefault(doi_key, []).append(candidate)

        if candidate.arxiv_id:
            arxiv_key = candidate.arxiv_id.lower().strip()
            arxiv_map.setdefault(arxiv_key, []).append(candidate)

        if candidate.semantic_scholar_id:
            ss_key = candidate.semantic_scholar_id.lower().strip()
            ss_map.setdefault(ss_key, []).append(candidate)

        # 所有论文都按标准化标题索引
        title_key = _normalize_title(candidate.title)
        if title_key:
            title_map.setdefault(title_key, []).append(candidate)

    # 第二轮：去重和合并
    seen = set()
    seen_paper_ids = set()
    result = []

    for candidate in candidates:
        # 生成唯一标识
        candidate_id = id(candidate)
        if candidate_id in seen:
            continue

        # 跳过 paper_id 已在结果中的（可能通过不同 key 被合并过）
        if candidate.paper_id in seen_paper_ids:
            seen.add(candidate_id)
            continue

        # 找到所有重复的候选
        duplicates = []

        # 按 DOI 查找
        if candidate.doi:
            doi_key = candidate.doi.lower().strip()
            duplicates.extend(doi_map.get(doi_key, []))

        # 按 arXiv ID 查找
        if candidate.arxiv_id:
            arxiv_key = candidate.arxiv_id.lower().strip()
            duplicates.extend(arxiv_map.get(arxiv_key, []))

        # 按 Semantic Scholar ID 查找
        if candidate.semantic_scholar_id:
            ss_key = candidate.semantic_scholar_id.lower().strip()
            duplicates.extend(ss_map.get(ss_key, []))

        # 按标准化标题查找（作为兜底）
        title_key = _normalize_title(candidate.title)
        if title_key and not candidate.doi and not candidate.arxiv_id and not candidate.semantic_scholar_id:
            duplicates.extend(title_map.get(title_key, []))

        # 去重 duplicates 列表
        unique_duplicates = []
        dup_ids = set()
        for dup in duplicates:
            dup_id = id(dup)
            if dup_id not in dup_ids:
                unique_duplicates.append(dup)
                dup_ids.add(dup_id)

        # 如果只有自己，直接添加
        if len(unique_duplicates) <= 1:
            seen.add(candidate_id)
            seen_paper_ids.add(candidate.paper_id)
            result.append(candidate)
            continue

        # 有重复，选择优先级最高的作为基础
        # 优先级: zotero > semantic_scholar > arxiv
        priority_order = {"zotero": 0, "semantic_scholar": 1, "arxiv": 2}
        base = min(unique_duplicates, key=lambda c: priority_order.get(c.source, 999))

        # 如果 base 的 paper_id 已经在结果中，只标记已处理但不重复添加
        if base.paper_id in seen_paper_ids:
            for dup in unique_duplicates:
                seen.add(id(dup))
            continue

        # 合并元数据
        merged = base.model_copy()

        for dup in unique_duplicates:
            # 标记为已处理
            seen.add(id(dup))

            # 合并 IDs
            if not merged.doi and dup.doi:
                merged.doi = dup.doi
            if not merged.arxiv_id and dup.arxiv_id:
                merged.arxiv_id = dup.arxiv_id
            if not merged.semantic_scholar_id and dup.semantic_scholar_id:
                merged.semantic_scholar_id = dup.semantic_scholar_id
            if not merged.zotero_item_id and dup.zotero_item_id:
                merged.zotero_item_id = dup.zotero_item_id

            # 合并 citation_count（取最大值）
            if dup.citation_count is not None:
                if merged.citation_count is None:
                    merged.citation_count = dup.citation_count
                else:
                    merged.citation_count = max(merged.citation_count, dup.citation_count)

            # 合并 PDF URL（优先保留非空的）
            if not merged.pdf_url and dup.pdf_url:
                merged.pdf_url = dup.pdf_url

            # 合并 local_pdf_path（优先保留非空的）
            if not merged.local_pdf_path and dup.local_pdf_path:
                merged.local_pdf_path = dup.local_pdf_path

            # 合并其他可选字段
            if not merged.venue and dup.venue:
                merged.venue = dup.venue
            if not merged.abstract and dup.abstract:
                merged.abstract = dup.abstract
            if not merged.url and dup.url:
                merged.url = dup.url
            if not merged.year and dup.year:
                merged.year = dup.year

            # 合并作者列表（如果 base 为空）
            if not merged.authors and dup.authors:
                merged.authors = dup.authors

        seen_paper_ids.add(merged.paper_id)
        result.append(merged)

    return result
