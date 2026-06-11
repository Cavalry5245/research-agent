from __future__ import annotations

from pathlib import Path
from typing import Any

from app.research_workflow.tool_registry import ToolHealth


class ZoteroAdapter:
    def __init__(self, provider: str = "local_http") -> None:
        self.provider = provider

    def health(self) -> ToolHealth:
        return ToolHealth(
            tool_name="zotero.list_collection_items",
            provider=self.provider,
            available=True,
            fallback_available=True,
            fallback_active=True,
            message="Zotero local HTTP fallback is configured",
        )


class ObsidianAdapter:
    def __init__(self, vault_root: str | Path) -> None:
        self.vault_root = Path(vault_root)

    def health(self) -> ToolHealth:
        return ToolHealth(
            tool_name="obsidian.publish_markdown",
            provider="direct_markdown",
            available=True,
            fallback_available=True,
            fallback_active=True,
            message="Direct Markdown publishing is available",
        )

    def publish_markdown(self, note_name: str, content: str) -> dict[str, Any]:
        relative_path = self._safe_relative_markdown_path(note_name)
        target = (self.vault_root / relative_path).resolve()
        vault = self.vault_root.resolve()
        if not _is_relative_to(target, vault):
            raise ValueError("Obsidian note path must stay inside the vault root")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "path": str(target),
            "provider": "direct_markdown",
            "fallback_used": True,
        }

    def _safe_relative_markdown_path(self, note_name: str) -> Path:
        raw = Path(note_name)
        if raw.is_absolute():
            raise ValueError("Obsidian note path must be relative")
        if any(part == ".." for part in raw.parts):
            raise ValueError("Obsidian note path cannot contain parent traversal")
        if not raw.name:
            raise ValueError("Obsidian note path is empty")
        if raw.suffix.lower() != ".md":
            raw = raw.with_suffix(".md")
        return raw


class SemanticScholarAdapter:
    def __init__(self, available: bool = False) -> None:
        self.available = available

    def health(self) -> ToolHealth:
        return ToolHealth(
            tool_name="semantic_scholar.enrich",
            provider="semantic_scholar" if self.available else "local_metadata",
            available=self.available,
            fallback_available=True,
            fallback_active=not self.available,
            message=(
                "Semantic Scholar adapter available"
                if self.available
                else "Using local metadata fallback"
            ),
        )

    def enrich(self, metadata: dict[str, Any]) -> dict[str, Any]:
        title = str(metadata.get("title") or metadata.get("paper_title") or "Untitled")
        return {
            "title": title,
            "doi": metadata.get("doi"),
            "year": metadata.get("year"),
            "citation_count": metadata.get("citation_count"),
            "references": metadata.get("references", []),
            "related_papers": [],
            "provider": "semantic_scholar" if self.available else "local_metadata",
            "fallback_used": not self.available,
            "summary": f"Local metadata available for {title}",
        }


class ArxivAdapter:
    def __init__(self, available: bool = False) -> None:
        self.available = available

    def health(self) -> ToolHealth:
        return ToolHealth(
            tool_name="arxiv.find_preprint",
            provider="arxiv" if self.available else "local_metadata",
            available=self.available,
            fallback_available=True,
            fallback_active=not self.available,
            message="arXiv adapter available" if self.available else "Using Zotero/local PDF fallback",
        )

    def find_preprint(self, metadata: dict[str, Any]) -> dict[str, Any]:
        title = str(metadata.get("title") or metadata.get("paper_title") or "Untitled")
        return {
            "title": title,
            "arxiv_id": metadata.get("arxiv_id"),
            "url": metadata.get("url"),
            "pdf_path": metadata.get("pdf_path"),
            "provider": "arxiv" if self.available else "local_metadata",
            "fallback_used": not self.available,
            "summary": f"Using local paper source for {title}",
        }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
