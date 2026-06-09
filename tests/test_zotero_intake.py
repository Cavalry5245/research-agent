from pathlib import Path

from app.research_workflow.zotero_intake import (
    CollectionIntakeService,
    ZoteroAttachment,
    ZoteroCollectionItem,
    ZoteroLocalHttpClient,
    resolve_first_existing_pdf,
)


class FakeZoteroClient:
    def __init__(self, items):
        self.items = items
        self.seen_collection_ids = []

    def list_collection_items(self, collection_id: str):
        self.seen_collection_ids.append(collection_id)
        return self.items


def test_collection_intake_limits_and_normalizes_items(tmp_path):
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"%PDF fake a")
    pdf_b.write_bytes(b"%PDF fake b")
    client = FakeZoteroClient(
        [
            ZoteroCollectionItem(
                key="A1",
                title="Paper A",
                creators=["Alice", "Bob"],
                year=2025,
                doi="10.1/a",
                url="https://example.test/a",
                attachments=[ZoteroAttachment(key="ATT1", title="A PDF", path=str(pdf_a))],
                raw={"itemType": "journalArticle"},
            ),
            ZoteroCollectionItem(
                key="B2",
                title="Paper B",
                creators=[],
                year=None,
                doi=None,
                url=None,
                attachments=[ZoteroAttachment(key="ATT2", title="B PDF", path=str(pdf_b))],
                raw={},
            ),
        ]
    )
    service = CollectionIntakeService(client)

    items = service.collect_items("COLL123", max_papers=1)

    assert client.seen_collection_ids == ["COLL123"]
    assert len(items) == 1
    assert items[0].item_id == "zotero_A1"
    assert items[0].zotero_item_id == "A1"
    assert items[0].title == "Paper A"
    assert items[0].pdf_path == str(pdf_a)
    assert items[0].metadata["creators"] == ["Alice", "Bob"]
    assert items[0].metadata["doi"] == "10.1/a"
    assert items[0].status == "queued"


def test_collection_intake_marks_missing_pdf_as_skipped():
    client = FakeZoteroClient(
        [
            ZoteroCollectionItem(
                key="NOFILE",
                title="Missing PDF Paper",
                attachments=[ZoteroAttachment(key="ATT", title="Missing", path="Z:/missing.pdf")],
                raw={},
            )
        ]
    )
    service = CollectionIntakeService(client)

    items = service.collect_items("COLL123", max_papers=5)

    assert items[0].status == "skipped"
    assert items[0].pdf_path is None
    assert "No local PDF attachment found" in items[0].error


def test_resolve_first_existing_pdf_handles_absolute_and_file_uri(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF fake")

    assert resolve_first_existing_pdf([str(pdf)]) == str(pdf)
    assert resolve_first_existing_pdf([pdf.as_uri()]) == str(pdf)
    assert resolve_first_existing_pdf(["", "Z:/missing.pdf"]) is None


def test_zotero_local_http_client_normalizes_local_api_payload(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "key": "A1",
                    "data": {
                        "title": "Paper A",
                        "creators": [
                            {"firstName": "Alice", "lastName": "Zhang"},
                            {"name": "Research Group"},
                        ],
                        "date": "2025-04-01",
                        "DOI": "10.1/a",
                        "url": "https://example.test/a",
                    },
                    "links": {
                        "attachment": {
                            "href": "file:///C:/Users/HC/Zotero/storage/A1/paper.pdf"
                        }
                    },
                }
            ]

    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    client = ZoteroLocalHttpClient(base_url="http://127.0.0.1:23119/api")

    items = client.list_collection_items("COLL123")

    assert calls[0][0].endswith("/collections/COLL123/items")
    assert items[0].key == "A1"
    assert items[0].title == "Paper A"
    assert items[0].creators == ["Alice Zhang", "Research Group"]
    assert items[0].year == 2025
    assert items[0].doi == "10.1/a"
    assert items[0].attachments[0].path == "file:///C:/Users/HC/Zotero/storage/A1/paper.pdf"
