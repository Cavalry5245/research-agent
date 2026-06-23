from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, unquote, urlparse

import httpx
from pydantic import BaseModel, Field

from app.research_workflow.schemas import ResearchRunPaperItem


class ZoteroAttachment(BaseModel):
    key: str
    title: str = ""
    path: str | None = None
    content_type: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ZoteroCollection(BaseModel):
    key: str
    name: str
    parent_key: str | None = None
    num_items: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ZoteroCollectionItem(BaseModel):
    key: str
    title: str
    creators: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    attachments: list[ZoteroAttachment] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ZoteroCollectionClient(Protocol):
    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        ...


def resolve_first_existing_pdf(paths: list[str | None]) -> str | None:
    for raw_path in paths:
        if not raw_path:
            continue
        candidate = _normalize_pdf_path(raw_path)
        if candidate and candidate.suffix.lower() == ".pdf" and candidate.is_file():
            return str(candidate)
    return None


def _normalize_pdf_path(raw_path: str) -> Path | None:
    local_path = Path(raw_path).expanduser()
    if local_path.is_absolute():
        return local_path

    parsed = urlparse(raw_path)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc.lower() != "localhost":
            normalized = f"//{parsed.netloc}{parsed.path}"
        else:
            normalized = parsed.path
        # Handle Windows-style file: paths with backslashes
        # e.g. "file:\D:\HC\Zotero\storage\file.pdf" → "D:\HC\Zotero\storage\file.pdf"
        if normalized.startswith("\\") and len(normalized) > 3 and normalized[2] == ":":
            normalized = normalized.lstrip("\\")
        normalized = unquote(normalized)
        if len(normalized) >= 4 and normalized[0] == "/" and normalized[2] == ":":
            normalized = normalized[1:]
        return Path(normalized).expanduser()
    if parsed.scheme:
        return None
    return local_path


class ZoteroLocalHttpClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:23119/api",
        library_path: str = "users/0",
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.library_path = library_path.strip("/")
        self.timeout = timeout
        # Disable proxy auto-detection to avoid Windows system proxy interference.
        # httpx defaults to trust_env=True which reads system proxy settings
        # (e.g. Clash at 127.0.0.1:7890) and causes [Errno 2] errors on local calls.
        self._client = httpx.Client(trust_env=False)

    def list_collections(self, limit: int = 100) -> list[ZoteroCollection]:
        response = self._client.get(
            f"{self._library_url}/collections?limit={int(limit)}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return [_collection_from_local_api(raw) for raw in response.json()]

    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        response = self._client.get(
            f"{self._library_url}/collections/{quote(collection_id, safe='')}/items",
            timeout=self.timeout,
        )
        response.raise_for_status()
        items: list[ZoteroCollectionItem] = []
        for raw in response.json():
            child_attachments = self._list_child_attachments(raw)
            items.append(_item_from_local_api(raw, child_attachments=child_attachments))
        return items

    @property
    def _library_url(self) -> str:
        if not self.library_path:
            return self.base_url
        return f"{self.base_url}/{self.library_path}"

    def _list_child_attachments(self, raw: dict[str, Any]) -> list[ZoteroAttachment]:
        data = raw.get("data") or raw
        if data.get("itemType") == "attachment":
            return []
        item_key = str(raw.get("key") or data.get("key") or "")
        if not item_key:
            return []

        try:
            response = self._client.get(
                f"{self._library_url}/items/{quote(item_key, safe='')}/children",
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        return _attachments_from_local_child_items(response.json())


class CollectionIntakeService:
    def __init__(self, client: ZoteroCollectionClient) -> None:
        self._client = client

    def collect_items(
        self,
        collection_id: str,
        max_papers: int,
    ) -> list[ResearchRunPaperItem]:
        now = datetime.now(timezone.utc)
        zotero_items = self._client.list_collection_items(collection_id)[:max_papers]
        paper_items: list[ResearchRunPaperItem] = []

        for item in zotero_items:
            pdf_path = resolve_first_existing_pdf(
                [attachment.path for attachment in item.attachments]
            )
            metadata = {
                "creators": item.creators,
                "year": item.year,
                "doi": item.doi,
                "url": item.url,
                "attachments": [attachment.model_dump() for attachment in item.attachments],
                "zotero": item.raw,
            }
            update: dict[str, Any] = {
                "item_id": f"zotero_{item.key}",
                "title": item.title,
                "zotero_item_id": item.key,
                "pdf_path": pdf_path,
                "metadata": metadata,
                "created_at": now,
                "updated_at": now,
            }
            if pdf_path is None:
                update.update(
                    {
                        "status": "skipped",
                        "progress": 1.0,
                        "error": "No local PDF attachment found",
                        "completed_at": now,
                    }
                )
            paper_items.append(ResearchRunPaperItem(**update))

        return paper_items


def _item_from_local_api(
    raw: dict[str, Any],
    child_attachments: list[ZoteroAttachment] | None = None,
) -> ZoteroCollectionItem:
    data = raw.get("data") or raw
    return ZoteroCollectionItem(
        key=str(raw.get("key") or data.get("key") or ""),
        title=str(data.get("title") or "Untitled Zotero item"),
        creators=_creators_from_data(data),
        year=_year_from_date(data.get("date")),
        doi=data.get("DOI") or data.get("doi"),
        url=data.get("url"),
        attachments=[
            *_attachments_from_local_payload(raw),
            *(child_attachments or []),
        ],
        raw=raw,
    )


def _collection_from_local_api(raw: dict[str, Any]) -> ZoteroCollection:
    data = raw.get("data") or raw
    key = str(raw.get("key") or data.get("key") or "")
    meta = raw.get("meta") or {}
    num_items = meta.get("numItems")
    if num_items is not None:
        num_items = int(num_items)

    return ZoteroCollection(
        key=key,
        name=str(data.get("name") or key),
        parent_key=data.get("parentCollection") or None,
        num_items=num_items,
        raw=raw,
    )


def _attachments_from_local_payload(raw: dict[str, Any]) -> list[ZoteroAttachment]:
    data = raw.get("data") or raw
    attachments: list[ZoteroAttachment] = []

    for raw_attachment in raw.get("attachments", []) or data.get("attachments", []):
        attachment_data = raw_attachment.get("data") or raw_attachment
        attachments.append(
            ZoteroAttachment(
                key=str(raw_attachment.get("key") or attachment_data.get("key") or ""),
                title=str(attachment_data.get("title") or ""),
                path=attachment_data.get("path") or attachment_data.get("localPath"),
                content_type=attachment_data.get("contentType"),
                raw=raw_attachment,
            )
        )

    attachment_href = _attachment_href(raw)
    if attachment_href:
        attachments.append(
            ZoteroAttachment(
                key="attachment_link",
                title="Zotero attachment link",
                path=attachment_href,
                raw=(raw.get("links") or {}).get("attachment") or {},
            )
        )

    return attachments


def _attachments_from_local_child_items(
    child_items: list[dict[str, Any]],
) -> list[ZoteroAttachment]:
    attachments: list[ZoteroAttachment] = []
    for raw_child in child_items:
        attachment = _attachment_from_local_child_item(raw_child)
        if attachment is not None:
            attachments.append(attachment)
    return attachments


def _attachment_from_local_child_item(
    raw_child: dict[str, Any],
) -> ZoteroAttachment | None:
    data = raw_child.get("data") or raw_child
    if data.get("itemType") != "attachment":
        return None
    return ZoteroAttachment(
        key=str(raw_child.get("key") or data.get("key") or ""),
        title=str(data.get("title") or ""),
        path=data.get("path") or data.get("localPath") or _attachment_href(raw_child),
        content_type=data.get("contentType"),
        raw=raw_child,
    )


def _attachment_href(raw: dict[str, Any]) -> str | None:
    links = raw.get("links") or {}
    for link_name in ("enclosure", "attachment"):
        attachment_link = links.get(link_name)
        if isinstance(attachment_link, dict) and attachment_link.get("href"):
            return str(attachment_link["href"])
    return None


def _creators_from_data(data: dict[str, Any]) -> list[str]:
    creators: list[str] = []
    for creator in data.get("creators", []) or []:
        if creator.get("name"):
            creators.append(str(creator["name"]))
            continue
        name = " ".join(
            str(part)
            for part in (creator.get("firstName"), creator.get("lastName"))
            if part
        ).strip()
        if name:
            creators.append(name)
    return creators


def _year_from_date(value: Any) -> int | None:
    if not value:
        return None
    for token in str(value).replace("/", "-").split("-"):
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None
