from pathlib import Path

from app.research_workflow.tool_adapters import (
    ArxivAdapter,
    ObsidianAdapter,
    SemanticScholarAdapter,
    ZoteroAdapter,
)


def test_zotero_adapter_reports_local_http_fallback_health():
    health = ZoteroAdapter().health()

    assert health.tool_name == "zotero.list_collection_items"
    assert health.provider == "local_http"
    assert health.available is True
    assert health.fallback_available is True
    assert health.fallback_active is True
    assert "fallback" in health.message.lower()


def test_obsidian_adapter_publishes_markdown_inside_vault(tmp_path):
    adapter = ObsidianAdapter(tmp_path)

    result = adapter.publish_markdown(
        "Literature Reviews/IRSTD Review",
        "# IRSTD Review\n\nEvidence linked.",
    )

    path = Path(result["path"])
    assert path == tmp_path / "Literature Reviews" / "IRSTD Review.md"
    assert path.read_text(encoding="utf-8").startswith("# IRSTD Review")
    assert result["provider"] == "direct_markdown"
    assert result["fallback_used"] is True


def test_obsidian_adapter_rejects_paths_outside_vault(tmp_path):
    adapter = ObsidianAdapter(tmp_path)

    for unsafe_name in ("../escape.md", str((tmp_path / ".." / "escape.md").resolve())):
        try:
            adapter.publish_markdown(unsafe_name, "bad")
        except ValueError as exc:
            assert "vault root" in str(exc) or "relative" in str(exc) or "parent" in str(exc)
        else:
            raise AssertionError("Expected unsafe Obsidian path to be rejected")


def test_semantic_scholar_adapter_uses_local_metadata_fallback():
    adapter = SemanticScholarAdapter(available=False)

    result = adapter.enrich(
        {
            "title": "Grounding DINO",
            "doi": "10.1234/demo",
            "year": 2025,
        }
    )
    health = adapter.health()

    assert result["title"] == "Grounding DINO"
    assert result["doi"] == "10.1234/demo"
    assert result["provider"] == "local_metadata"
    assert result["fallback_used"] is True
    assert health.available is False
    assert health.fallback_active is True


def test_arxiv_adapter_uses_local_pdf_fallback():
    adapter = ArxivAdapter(available=False)

    result = adapter.find_preprint(
        {
            "title": "Infrared Small Target Detection",
            "url": "https://example.test/paper",
            "pdf_path": "C:/papers/demo.pdf",
        }
    )
    health = adapter.health()

    assert result["title"] == "Infrared Small Target Detection"
    assert result["url"] == "https://example.test/paper"
    assert result["pdf_path"] == "C:/papers/demo.pdf"
    assert result["provider"] == "local_metadata"
    assert result["fallback_used"] is True
    assert health.available is False
    assert health.fallback_available is True
