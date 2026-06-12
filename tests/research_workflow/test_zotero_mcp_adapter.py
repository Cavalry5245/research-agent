from app.mcp.schemas import MCPToolResult
from app.research_workflow.zotero_mcp_adapter import ZoteroMCPAdapter


class FakeProxy:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def call_tool(self, call):
        self.calls.append(call)
        return self.result


def test_zotero_mcp_adapter_calls_collection_tool():
    proxy = FakeProxy(
        MCPToolResult(
            status="success",
            result=[
                {
                    "key": "ABCD1234",
                    "title": "Demo Paper",
                    "creators": ["Ada Lovelace"],
                    "year": 2026,
                    "doi": "10.1234/demo",
                    "url": "https://example.test/demo",
                    "attachments": [
                        {
                            "key": "PDF12345",
                            "title": "PDF",
                            "path": "D:/papers/demo.pdf",
                            "content_type": "application/pdf",
                        }
                    ],
                }
            ],
            duration_ms=10.0,
            server_name="zotero",
            tool_name="zotero_get_collection_items",
        )
    )

    adapter = ZoteroMCPAdapter(proxy)
    items = adapter.list_collection_items("COLL123")

    assert proxy.calls[0].server_name == "zotero"
    assert proxy.calls[0].tool_name == "zotero_get_collection_items"
    assert proxy.calls[0].arguments == {"collection_key": "COLL123", "detail": "full"}
    assert items[0].key == "ABCD1234"
    assert items[0].title == "Demo Paper"
    assert items[0].attachments[0].path == "D:/papers/demo.pdf"


def test_zotero_mcp_adapter_parses_markdown_collection_items():
    proxy = FakeProxy(
        MCPToolResult(
            status="success",
            result="\n".join(
                [
                    "# Items in Collection: Demo (1 items)",
                    "",
                    "## 1. Markdown Paper",
                    "**Type:** journalArticle",
                    "**Item Key:** MKDN1234",
                    "**Date:** 2026-05-01",
                    "**Authors:** Lovelace, Ada; Hopper, Grace",
                    "**Attachments:** PDF, Notes",
                    "",
                ]
            ),
            duration_ms=10.0,
            server_name="zotero",
            tool_name="zotero_get_collection_items",
        )
    )

    items = ZoteroMCPAdapter(proxy).list_collection_items("COLL123")

    assert items[0].key == "MKDN1234"
    assert items[0].title == "Markdown Paper"
    assert items[0].year == 2026
    assert items[0].creators == ["Lovelace, Ada", "Hopper, Grace"]
    assert items[0].attachments[0].content_type == "application/pdf"


def test_zotero_mcp_adapter_raises_on_tool_error():
    proxy = FakeProxy(
        MCPToolResult(
            status="error",
            error="zotero unavailable",
            duration_ms=10.0,
            server_name="zotero",
            tool_name="zotero_get_collection_items",
        )
    )

    adapter = ZoteroMCPAdapter(proxy)

    try:
        adapter.list_collection_items("COLL123")
    except RuntimeError as exc:
        assert "zotero unavailable" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
