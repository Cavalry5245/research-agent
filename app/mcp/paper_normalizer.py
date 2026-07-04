"""Normalization utilities for academic paper search results.

Different MCP search sources return different dict layouts:

* the external ``paper-search-mcp`` server returns its ``Paper.to_dict()``
  shape (``paper_id`` / ``authors`` as ``"; "``-joined string / ...),
* the project's own ``minimal_arxiv_server`` returns ``{id, pdf_url,
  published, authors: list[str], ...}``,
* the project's own ``minimal_semantic_scholar_server`` returns raw
  Semantic Scholar items (``paperId`` / ``authors: list[dict]`` /
  ``openAccessPdf.url`` / ``citationCount`` ...).

``normalize_paper`` maps any of these onto the unified
:class:`app.mcp.schemas.Paper` so downstream workflow code never branches on
source. ``dedupe_papers`` merges duplicates across sources.
"""

from __future__ import annotations

import re
from typing import Any

from app.mcp.schemas import Paper

_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def extract_doi(text: str) -> str:
    """Extract a DOI from arbitrary text or a URL, or ``""`` if none."""
    if not text:
        return ""
    match = _DOI_PATTERN.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(".,;)")


def _normalize_authors(raw: Any) -> list[str]:
    """Coerce author payloads in any common shape to a list of names."""
    if not raw:
        return []
    if isinstance(raw, str):
        # paper-search-mcp joins authors with "; "
        return [name.strip() for name in raw.split(";") if name.strip()]
    if isinstance(raw, list):
        names: list[str] = []
        for item in raw:
            if isinstance(item, str):
                if item.strip():
                    names.append(item.strip())
            elif isinstance(item, dict):
                name = (item.get("name") or item.get("authorName") or "").strip()
                if name:
                    names.append(name)
        return names
    return []


def _split_semicolon(value: Any) -> list[str]:
    if not value or not isinstance(value, str):
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coerce_year(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_paper(raw: dict[str, Any], source_hint: str = "") -> Paper:
    """Map a source-specific paper dict onto the unified :class:`Paper`."""
    if not isinstance(raw, dict):
        return Paper(source=source_hint)

    abstract = (raw.get("abstract") or raw.get("summary") or "").strip()
    url = (raw.get("url") or "").strip()
    doi = (raw.get("doi") or "").strip() or extract_doi(abstract) or extract_doi(url)

    open_access_pdf = raw.get("openAccessPdf")
    pdf_url = (raw.get("pdf_url") or "").strip()
    if not pdf_url and isinstance(open_access_pdf, dict):
        pdf_url = (open_access_pdf.get("url") or "").strip()

    published_date = (
        raw.get("published_date") or raw.get("published") or raw.get("publicationDate")
    )
    published_date = published_date.strip() if isinstance(published_date, str) else None

    extra: dict[str, Any] = {}
    categories = _split_semicolon(raw.get("categories"))
    if categories:
        extra["categories"] = categories
    keywords = _split_semicolon(raw.get("keywords"))
    if keywords:
        extra["keywords"] = keywords
    venue = (raw.get("venue") or "").strip()
    if venue:
        extra["venue"] = venue
    reference_count = _coerce_int(raw.get("reference_count") or raw.get("referenceCount"))
    if reference_count:
        extra["reference_count"] = reference_count

    return Paper(
        paper_id=(
            raw.get("paper_id")
            or raw.get("id")
            or raw.get("paperId")
            or doi
            or ""
        ).strip(),
        title=(raw.get("title") or "").strip(),
        authors=_normalize_authors(raw.get("authors")),
        abstract=abstract,
        doi=doi,
        pdf_url=pdf_url,
        url=url,
        source=(raw.get("source") or source_hint or "").strip(),
        published_date=published_date,
        year=_coerce_year(raw.get("year")),
        citation_count=_coerce_int(
            raw.get("citation_count") or raw.get("citations") or raw.get("citationCount")
        ),
        extra=extra,
    )


def _paper_unique_key(paper: Paper) -> str:
    doi = (paper.doi or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = (paper.title or "").strip().lower()
    if title:
        return f"title:{title}|authors:{'|'.join(a.lower() for a in paper.authors)}"
    return f"id:{(paper.paper_id or '').strip().lower()}"


def dedupe_papers(papers: list[Paper]) -> list[Paper]:
    """Deduplicate papers by DOI > title+authors > paper_id, preserving order."""
    deduped: list[Paper] = []
    seen: set[str] = set()
    for paper in papers:
        key = _paper_unique_key(paper)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(paper)
    return deduped
