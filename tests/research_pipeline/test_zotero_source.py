"""
Tests for Zotero Source Adapter

测试 Zotero source adapter，包括 collection 列表和 candidate 导入。
"""

from unittest.mock import Mock, patch

import pytest

from app.research_pipeline.schemas import PaperCandidate
from app.research_pipeline.sources.zotero import ZoteroSourceAdapter
from app.research_workflow.zotero_intake import (
    ZoteroCollection,
    ZoteroCollectionItem,
    ZoteroAttachment,
)


class TestZoteroSourceAdapter:
    """测试 Zotero source adapter"""

    def test_list_collections_success(self):
        """测试成功获取 collection 列表"""
        # Mock client
        mock_client = Mock()
        mock_client.list_collections.return_value = [
            ZoteroCollection(
                key="COLL001",
                name="Machine Learning Papers",
                parent_key=None,
                num_items=15,
                raw={},
            ),
            ZoteroCollection(
                key="COLL002",
                name="Deep Learning",
                parent_key="COLL001",
                num_items=8,
                raw={},
            ),
        ]

        adapter = ZoteroSourceAdapter(client=mock_client)
        collections = adapter.list_collections()

        assert len(collections) == 2
        assert collections[0]["key"] == "COLL001"
        assert collections[0]["name"] == "Machine Learning Papers"
        assert collections[0]["num_items"] == 15
        assert collections[1]["key"] == "COLL002"
        assert collections[1]["parent_key"] == "COLL001"

    def test_list_collections_empty(self):
        """测试空 collection 列表"""
        mock_client = Mock()
        mock_client.list_collections.return_value = []

        adapter = ZoteroSourceAdapter(client=mock_client)
        collections = adapter.list_collections()

        assert collections == []

    def test_get_candidates_with_pdf(self):
        """测试获取带 PDF 的候选论文"""
        mock_client = Mock()
        mock_client.list_collection_items.return_value = [
            ZoteroCollectionItem(
                key="ITEM001",
                title="Attention Is All You Need",
                creators=["Ashish Vaswani", "Noam Shazeer"],
                year=2017,
                doi="10.5555/3295222.3295349",
                url="https://arxiv.org/abs/1706.03762",
                attachments=[
                    ZoteroAttachment(
                        key="ATT001",
                        title="Full Text PDF",
                        path="E:\\papers\\attention.pdf",
                        content_type="application/pdf",
                        raw={},
                    ),
                ],
                raw={
                    "key": "ITEM001",
                    "data": {
                        "title": "Attention Is All You Need",
                        "creators": [
                            {"creatorType": "author", "firstName": "Ashish", "lastName": "Vaswani"},
                        ],
                        "date": "2017",
                        "DOI": "10.5555/3295222.3295349",
                        "url": "https://arxiv.org/abs/1706.03762",
                        "extra": "arXiv:1706.03762",
                    },
                },
            ),
        ]

        adapter = ZoteroSourceAdapter(client=mock_client)
        candidates = adapter.get_candidates(collection_key="COLL001")

        assert len(candidates) == 1
        candidate = candidates[0]
        assert isinstance(candidate, PaperCandidate)
        assert candidate.source == "zotero"
        assert candidate.title == "Attention Is All You Need"
        assert candidate.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert candidate.year == 2017
        assert candidate.doi == "10.5555/3295222.3295349"
        assert candidate.zotero_item_id == "ITEM001"
        assert candidate.local_pdf_path == "E:\\papers\\attention.pdf"
        assert candidate.arxiv_id == "1706.03762"

    def test_get_candidates_without_pdf(self):
        """测试无 PDF 时仍生成 candidate"""
        mock_client = Mock()
        mock_client.list_collection_items.return_value = [
            ZoteroCollectionItem(
                key="ITEM002",
                title="Paper Without PDF",
                creators=["John Doe"],
                year=2024,
                doi="10.1234/test",
                url="https://example.com/paper",
                attachments=[],
                raw={
                    "key": "ITEM002",
                    "data": {
                        "title": "Paper Without PDF",
                        "creators": [
                            {"creatorType": "author", "lastName": "Doe", "firstName": "John"},
                        ],
                        "date": "2024",
                        "DOI": "10.1234/test",
                    },
                },
            ),
        ]

        adapter = ZoteroSourceAdapter(client=mock_client)
        candidates = adapter.get_candidates(collection_key="COLL002")

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.source == "zotero"
        assert candidate.title == "Paper Without PDF"
        assert candidate.local_pdf_path is None  # 无 PDF
        assert candidate.zotero_item_id == "ITEM002"

    def test_get_candidates_multiple_papers(self):
        """测试获取多篇论文"""
        mock_client = Mock()
        mock_client.list_collection_items.return_value = [
            ZoteroCollectionItem(
                key=f"ITEM{i:03d}",
                title=f"Paper {i}",
                creators=[f"Author {i}"],
                year=2020 + i,
                doi=f"10.1234/paper{i}",
                url=f"https://example.com/paper{i}",
                attachments=[],
                raw={
                    "key": f"ITEM{i:03d}",
                    "data": {
                        "title": f"Paper {i}",
                        "creators": [{"creatorType": "author", "lastName": f"Author {i}"}],
                    },
                },
            )
            for i in range(1, 6)
        ]

        adapter = ZoteroSourceAdapter(client=mock_client)
        candidates = adapter.get_candidates(collection_key="COLL003")

        assert len(candidates) == 5
        for i, candidate in enumerate(candidates, start=1):
            assert candidate.title == f"Paper {i}"
            assert candidate.zotero_item_id == f"ITEM{i:03d}"

    def test_get_candidates_empty_collection(self):
        """测试空 collection"""
        mock_client = Mock()
        mock_client.list_collection_items.return_value = []

        adapter = ZoteroSourceAdapter(client=mock_client)
        candidates = adapter.get_candidates(collection_key="EMPTY_COLL")

        assert candidates == []

    def test_list_collections_http_error(self):
        """测试 Zotero API 失败时返回明确错误"""
        import httpx

        mock_client = Mock()
        mock_client.list_collections.side_effect = httpx.HTTPStatusError(
            "Connection failed",
            request=Mock(),
            response=Mock(status_code=500),
        )

        adapter = ZoteroSourceAdapter(client=mock_client)

        with pytest.raises(httpx.HTTPStatusError):
            adapter.list_collections()

    def test_get_candidates_http_error(self):
        """测试获取 items 时 API 失败"""
        import httpx

        mock_client = Mock()
        mock_client.list_collection_items.side_effect = httpx.HTTPStatusError(
            "Collection not found",
            request=Mock(),
            response=Mock(status_code=404),
        )

        adapter = ZoteroSourceAdapter(client=mock_client)

        with pytest.raises(httpx.HTTPStatusError):
            adapter.get_candidates(collection_key="INVALID_COLL")

    def test_resolve_local_pdf_path(self):
        """测试解析本地 PDF 路径"""
        mock_client = Mock()
        mock_client.list_collection_items.return_value = [
            ZoteroCollectionItem(
                key="ITEM003",
                title="PDF Test Paper",
                creators=["Test Author"],
                year=2023,
                doi=None,
                url=None,
                attachments=[
                    ZoteroAttachment(
                        key="ATT001",
                        title="Snapshot",
                        path=None,
                        content_type="text/html",
                        raw={},
                    ),
                    ZoteroAttachment(
                        key="ATT002",
                        title="Full Text PDF",
                        path="C:\\Users\\test\\papers\\test.pdf",
                        content_type="application/pdf",
                        raw={},
                    ),
                ],
                raw={
                    "key": "ITEM003",
                    "data": {
                        "title": "PDF Test Paper",
                    },
                },
            ),
        ]

        adapter = ZoteroSourceAdapter(client=mock_client)
        candidates = adapter.get_candidates(collection_key="COLL_PDF")

        assert len(candidates) == 1
        candidate = candidates[0]
        # 应该解析到第一个有效的 PDF 路径
        assert candidate.local_pdf_path == "C:\\Users\\test\\papers\\test.pdf"


class TestZoteroRouterIntegration:
    """测试 Zotero router 集成"""

    def test_list_collections_endpoint(self):
        """测试 list_zotero_collections 端点"""
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.research_pipeline.router.ZoteroSourceAdapter") as mock_adapter_class:
            mock_adapter = Mock()
            mock_adapter.list_collections.return_value = [
                {"key": "TEST001", "name": "Test Collection", "parent_key": None, "num_items": 5},
            ]
            mock_adapter_class.return_value = mock_adapter

            client = TestClient(app)
            response = client.get("/research-pipeline/sources/zotero/collections")

            assert response.status_code == 200
            data = response.json()
            assert "collections" in data
            assert "count" in data
            assert data["count"] == 1
            assert data["collections"][0]["key"] == "TEST001"

    def test_list_collections_endpoint_zotero_unavailable(self):
        """测试 Zotero 不可用时的错误处理"""
        from fastapi.testclient import TestClient
        from app.main import app
        import httpx

        with patch("app.research_pipeline.router.ZoteroSourceAdapter") as mock_adapter_class:
            mock_adapter = Mock()
            mock_adapter.list_collections.side_effect = httpx.ConnectError("Connection refused")
            mock_adapter_class.return_value = mock_adapter

            client = TestClient(app)
            response = client.get("/research-pipeline/sources/zotero/collections")

            assert response.status_code == 503
            response_data = response.json()
            # The error handler might wrap the response differently
            assert "Zotero API unavailable" in str(response_data)
