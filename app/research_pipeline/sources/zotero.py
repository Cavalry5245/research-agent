"""
Zotero Source Adapter

将 Zotero local API 集成到 research pipeline，提供 collection 列表和 candidate 导入能力。
"""

from typing import Any

from app.research_pipeline.schemas import PaperCandidate
from app.research_workflow.zotero_intake import ZoteroLocalHttpClient, _normalize_pdf_path


def _resolve_pdf_path_from_attachments(attachments: list[Any]) -> str | None:
    """
    从 attachments 中提取第一个 PDF 路径。

    对 Zotero API 返回的 URL 编码路径（含 %20 等）进行解码和归一化。

    Args:
        attachments: ZoteroAttachment 列表

    Returns:
        第一个 PDF 路径，如果没有则返回 None
    """
    for attachment in attachments:
        if not attachment.path:
            continue
        normalized = _normalize_pdf_path(attachment.path)
        if normalized and normalized.suffix.lower() == ".pdf":
            return str(normalized)
    return None


def _normalize_zotero_item_to_candidate(
    item: Any,  # ZoteroCollectionItem
) -> PaperCandidate:
    """
    将 ZoteroCollectionItem 归一化为 PaperCandidate。

    Args:
        item: ZoteroCollectionItem 实例

    Returns:
        归一化后的 PaperCandidate
    """
    # 提取本地 PDF 路径（不检查文件是否存在）
    local_pdf_path = _resolve_pdf_path_from_attachments(item.attachments)

    # 从 raw data 提取额外信息
    raw_data = item.raw.get("data", {})

    # 提取 arXiv ID（从 extra 字段）
    arxiv_id = None
    extra = raw_data.get("extra", "")
    if extra:
        import re

        match = re.search(r"arXiv:(\S+)", extra)
        if match:
            arxiv_id = match.group(1)

    # 提取 venue
    venue = raw_data.get("publicationTitle")

    # 提取摘要
    abstract = raw_data.get("abstractNote")

    return PaperCandidate(
        paper_id=item.key,
        source="zotero",
        title=item.title,
        authors=item.creators,
        year=item.year,
        venue=venue,
        abstract=abstract,
        doi=item.doi,
        arxiv_id=arxiv_id,
        semantic_scholar_id=None,
        zotero_item_id=item.key,
        url=item.url,
        pdf_url=None,
        local_pdf_path=local_pdf_path,
        citation_count=None,
        metadata={"zotero_raw": item.raw},
    )


class ZoteroSourceAdapter:
    """
    Zotero source adapter for research pipeline.

    Provides collection listing and paper candidate retrieval from Zotero.
    """

    def __init__(self, client: ZoteroLocalHttpClient | None = None) -> None:
        """
        初始化 Zotero source adapter。

        Args:
            client: ZoteroLocalHttpClient 实例。如果为 None，使用默认配置。
        """
        self.client = client or ZoteroLocalHttpClient()

    def list_collections(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        获取 Zotero collections 列表。

        Args:
            limit: 最多返回多少个 collections（默认 100）

        Returns:
            Collection 列表，每个元素包含 key, name, parent_key, num_items

        Raises:
            httpx.HTTPStatusError: Zotero API 调用失败
        """
        collections = self.client.list_collections(limit=limit)

        return [
            {
                "key": coll.key,
                "name": coll.name,
                "parent_key": coll.parent_key,
                "num_items": coll.num_items,
            }
            for coll in collections
        ]

    def get_candidates(self, collection_key: str) -> list[PaperCandidate]:
        """
        从指定 Zotero collection 获取候选论文。

        Args:
            collection_key: Zotero collection key

        Returns:
            候选论文列表（PaperCandidate）

        Raises:
            httpx.HTTPStatusError: Zotero API 调用失败
        """
        items = self.client.list_collection_items(collection_key)

        candidates = []
        for item in items:
            candidate = _normalize_zotero_item_to_candidate(item)
            candidates.append(candidate)

        return candidates
