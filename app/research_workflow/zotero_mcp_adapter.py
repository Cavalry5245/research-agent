from __future__ import annotations

import re
from typing import Any

from app.mcp.schemas import MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.zotero_intake import (
    ZoteroAttachment,
    ZoteroCollectionItem,
)


class ZoteroMCPAdapter:
    """Reads Zotero collection items through a standard MCP tool call."""

    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "zotero"

    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        result = self._proxy.call_tool(
            MCPToolCall(
                server_name=self._server_name,
                tool_name="zotero_get_collection_items",
                arguments={"collection_key": collection_id, "detail": "full"},
            )
        )
        if result.status != "success":
            raise RuntimeError(result.error or "Zotero MCP collection intake failed")
        return [_item_from_mcp_payload(item) for item in _normalize_mcp_items(result.result)]


def _normalize_mcp_items(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    if isinstance(payload, str):
        _raise_for_markdown_error(payload)
        return _items_from_markdown(payload)
    return []


def _item_from_mcp_payload(raw: dict[str, Any]) -> ZoteroCollectionItem:
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    return ZoteroCollectionItem(
        key=str(raw.get("key") or data.get("key") or ""),
        title=str(data.get("title") or raw.get("title") or "Untitled Zotero item"),
        creators=_creators_from_payload(data),
        year=_year_from_payload(data),
        doi=data.get("DOI") or data.get("doi"),
        url=data.get("url"),
        attachments=_attachments_from_payload(raw),
        raw=raw,
    )


def _attachments_from_payload(raw: dict[str, Any]) -> list[ZoteroAttachment]:
    attachments = raw.get("attachments") or (raw.get("data") or {}).get("attachments") or []
    parsed: list[ZoteroAttachment] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        data = attachment.get("data") if isinstance(attachment.get("data"), dict) else attachment
        parsed.append(
            ZoteroAttachment(
                key=str(attachment.get("key") or data.get("key") or ""),
                title=str(data.get("title") or ""),
                path=data.get("path") or data.get("localPath") or data.get("href"),
                content_type=data.get("content_type") or data.get("contentType"),
                raw=attachment,
            )
        )
    return parsed


def _creators_from_payload(data: dict[str, Any]) -> list[str]:
    creators = data.get("creators") or []
    if all(isinstance(item, str) for item in creators):
        return list(creators)
    names: list[str] = []
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        if creator.get("name"):
            names.append(str(creator["name"]))
            continue
        name = " ".join(
            str(part)
            for part in (creator.get("firstName"), creator.get("lastName"))
            if part
        ).strip()
        if name:
            names.append(name)
    return names


def _year_from_payload(data: dict[str, Any]) -> int | None:
    year = data.get("year")
    if isinstance(year, int):
        return year
    date = str(data.get("date") or "")
    for token in date.replace("/", "-").split("-"):
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None


def _items_from_markdown(markdown: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading = re.match(r"^##\s+(?:\d+\.\s+)?(.+)$", line)
        if heading:
            if current is not None:
                items.append(current)
            current = {"title": heading.group(1).strip(), "attachments": []}
            continue
        if current is None:
            continue
        if line.startswith("**Item Key:**"):
            current["key"] = line.split("**Item Key:**", 1)[1].strip()
        elif line.startswith("**Date:**"):
            current["date"] = line.split("**Date:**", 1)[1].strip()
        elif line.startswith("**Authors:**"):
            authors = line.split("**Authors:**", 1)[1].strip()
            if authors and authors != "No authors listed":
                current["creators"] = [part.strip() for part in authors.split(";") if part.strip()]
        elif line.startswith("**DOI:**"):
            current["doi"] = line.split("**DOI:**", 1)[1].strip()
        elif line.startswith("**URL:**"):
            current["url"] = line.split("**URL:**", 1)[1].strip()
        elif line.startswith("**Attachments:**") and "PDF" in line:
            current["attachments"] = [
                {
                    "key": "",
                    "title": "PDF attachment",
                    "content_type": "application/pdf",
                }
            ]

    if current is not None:
        items.append(current)
    return items


def _raise_for_markdown_error(markdown: str) -> None:
    text = markdown.strip()
    if not text:
        return
    lowered = text.lower()
    if lowered.startswith("no items found"):
        return
    if lowered.startswith("collection not found") or lowered.startswith("error fetching"):
        raise RuntimeError(text)
