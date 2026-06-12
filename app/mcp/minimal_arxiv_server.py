from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("arXiv")

ATOM = "{http://www.w3.org/2005/Atom}"


@mcp.tool(name="arxiv_search")
def arxiv_search(query: str, max_results: int = 5) -> dict[str, Any]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max(1, min(int(max_results), 20)),
    }
    try:
        response = httpx.get(
            "https://export.arxiv.org/api/query",
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        papers = _parse_arxiv_feed(response.text)
    except Exception as exc:
        return {
            "query": query,
            "papers": [],
            "fallback_used": True,
            "error": str(exc),
        }
    return {
        "query": query,
        "papers": papers,
        "fallback_used": False,
    }


def _parse_arxiv_feed(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    papers: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        links = [link.attrib for link in entry.findall(f"{ATOM}link")]
        pdf_url = next(
            (
                link.get("href")
                for link in links
                if link.get("title") == "pdf" or link.get("type") == "application/pdf"
            ),
            None,
        )
        papers.append(
            {
                "id": _text(entry, "id"),
                "title": _clean(_text(entry, "title")),
                "authors": [
                    _text(author, "name")
                    for author in entry.findall(f"{ATOM}author")
                    if _text(author, "name")
                ],
                "abstract": _clean(_text(entry, "summary")),
                "url": _text(entry, "id"),
                "pdf_url": pdf_url,
                "published": _text(entry, "published"),
                "updated": _text(entry, "updated"),
            }
        )
    return papers


def _text(element: ET.Element, name: str) -> str:
    child = element.find(f"{ATOM}{name}")
    return child.text.strip() if child is not None and child.text else ""


def _clean(value: str) -> str:
    return " ".join(value.split())


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
