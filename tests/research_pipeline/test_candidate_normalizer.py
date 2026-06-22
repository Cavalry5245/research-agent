"""
Tests for PaperCandidate Normalizer and Deduplication

测试三种来源的归一化和去重逻辑。
"""

import pytest

from app.research_pipeline.schemas import PaperCandidate
from app.research_pipeline.sources.normalizer import (
    normalize_arxiv_paper,
    normalize_semantic_scholar_paper,
    normalize_zotero_paper,
    deduplicate_candidates,
)


class TestSemanticScholarNormalization:
    """测试 Semantic Scholar 归一化"""

    def test_complete_paper(self):
        """测试完整论文数据"""
        raw = {
            "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
            "title": "Attention Is All You Need",
            "authors": [
                {"name": "Ashish Vaswani"},
                {"name": "Noam Shazeer"},
            ],
            "year": 2017,
            "venue": "NeurIPS",
            "abstract": "The dominant sequence transduction models...",
            "externalIds": {
                "DOI": "10.5555/3295222.3295349",
                "ArXiv": "1706.03762",
            },
            "url": "https://www.semanticscholar.org/paper/649def34f8be52c8b66281af98ae884c09aef38b",
            "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762.pdf"},
            "citationCount": 50000,
        }

        candidate = normalize_semantic_scholar_paper(raw)

        assert candidate.source == "semantic_scholar"
        assert candidate.title == "Attention Is All You Need"
        assert candidate.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert candidate.year == 2017
        assert candidate.venue == "NeurIPS"
        assert candidate.abstract == "The dominant sequence transduction models..."
        assert candidate.doi == "10.5555/3295222.3295349"
        assert candidate.arxiv_id == "1706.03762"
        assert candidate.semantic_scholar_id == "649def34f8be52c8b66281af98ae884c09aef38b"
        assert candidate.url == "https://www.semanticscholar.org/paper/649def34f8be52c8b66281af98ae884c09aef38b"
        assert candidate.pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"
        assert candidate.citation_count == 50000
        assert candidate.zotero_item_id is None
        assert candidate.local_pdf_path is None

    def test_minimal_paper(self):
        """测试最小必需字段"""
        raw = {
            "paperId": "abc123",
            "title": "Minimal Paper",
        }

        candidate = normalize_semantic_scholar_paper(raw)

        assert candidate.source == "semantic_scholar"
        assert candidate.title == "Minimal Paper"
        assert candidate.semantic_scholar_id == "abc123"
        assert candidate.authors == []
        assert candidate.year is None
        assert candidate.venue is None
        assert candidate.abstract is None
        assert candidate.doi is None
        assert candidate.arxiv_id is None
        assert candidate.citation_count is None

    def test_missing_optional_fields(self):
        """测试可选字段缺失时不会崩溃"""
        raw = {
            "paperId": "xyz789",
            "title": "Paper Without Optional Fields",
            "authors": [],
            "externalIds": {},
        }

        candidate = normalize_semantic_scholar_paper(raw)

        assert candidate.title == "Paper Without Optional Fields"
        assert candidate.authors == []
        assert candidate.doi is None
        assert candidate.arxiv_id is None


class TestArxivNormalization:
    """测试 arXiv 归一化"""

    def test_complete_paper(self):
        """测试完整论文数据"""
        raw = {
            "id": "http://arxiv.org/abs/1706.03762v5",
            "title": "Attention Is All You Need",
            "authors": [
                {"name": "Ashish Vaswani"},
                {"name": "Noam Shazeer"},
            ],
            "published": "2017-06-12T17:57:34Z",
            "summary": "The dominant sequence transduction models...",
            "arxiv_id": "1706.03762",
            "pdf_url": "http://arxiv.org/pdf/1706.03762v5",
            "doi": "10.5555/3295222.3295349",
        }

        candidate = normalize_arxiv_paper(raw)

        assert candidate.source == "arxiv"
        assert candidate.title == "Attention Is All You Need"
        assert candidate.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert candidate.year == 2017
        assert candidate.abstract == "The dominant sequence transduction models..."
        assert candidate.arxiv_id == "1706.03762"
        assert candidate.url == "http://arxiv.org/abs/1706.03762v5"
        assert candidate.pdf_url == "http://arxiv.org/pdf/1706.03762v5"
        assert candidate.doi == "10.5555/3295222.3295349"
        assert candidate.venue is None  # arXiv doesn't have venue
        assert candidate.semantic_scholar_id is None
        assert candidate.zotero_item_id is None

    def test_minimal_paper(self):
        """测试最小必需字段"""
        raw = {
            "id": "http://arxiv.org/abs/2401.12345v1",
            "title": "Minimal ArXiv Paper",
            "arxiv_id": "2401.12345",
        }

        candidate = normalize_arxiv_paper(raw)

        assert candidate.source == "arxiv"
        assert candidate.title == "Minimal ArXiv Paper"
        assert candidate.arxiv_id == "2401.12345"
        assert candidate.authors == []
        assert candidate.year is None
        assert candidate.abstract is None

    def test_year_extraction_from_published(self):
        """测试从 published 字段提取年份"""
        raw = {
            "id": "http://arxiv.org/abs/2024.01234",
            "title": "Test Paper",
            "arxiv_id": "2024.01234",
            "published": "2024-03-15T10:30:00Z",
        }

        candidate = normalize_arxiv_paper(raw)
        assert candidate.year == 2024

    def test_minimal_mcp_server_shape_extracts_stable_arxiv_id(self):
        """测试 minimal arXiv MCP server 返回结构可以生成非空唯一 paper_id"""
        raw = {
            "id": "http://arxiv.org/abs/2401.00001v2",
            "title": "A Paper About Agents",
            "authors": ["Ada Lovelace", "Grace Hopper"],
            "abstract": "This paper studies agent systems.",
            "pdf_url": "http://arxiv.org/pdf/2401.00001v2",
            "published": "2024-01-01T00:00:00Z",
        }

        candidate = normalize_arxiv_paper(raw)

        assert candidate.paper_id == "2401.00001"
        assert candidate.arxiv_id == "2401.00001"
        assert candidate.authors == ["Ada Lovelace", "Grace Hopper"]
        assert candidate.abstract == "This paper studies agent systems."


class TestZoteroNormalization:
    """测试 Zotero 归一化"""

    def test_complete_paper(self):
        """测试完整论文数据"""
        raw = {
            "key": "ABCD1234",
            "data": {
                "title": "Deep Learning for Vision",
                "creators": [
                    {"creatorType": "author", "firstName": "Geoffrey", "lastName": "Hinton"},
                    {"creatorType": "author", "firstName": "Yann", "lastName": "LeCun"},
                ],
                "date": "2015",
                "publicationTitle": "Nature",
                "abstractNote": "A comprehensive review of deep learning...",
                "DOI": "10.1038/nature14539",
                "url": "https://doi.org/10.1038/nature14539",
            },
        }

        candidate = normalize_zotero_paper(raw)

        assert candidate.source == "zotero"
        assert candidate.title == "Deep Learning for Vision"
        assert candidate.authors == ["Geoffrey Hinton", "Yann LeCun"]
        assert candidate.year == 2015
        assert candidate.venue == "Nature"
        assert candidate.abstract == "A comprehensive review of deep learning..."
        assert candidate.doi == "10.1038/nature14539"
        assert candidate.zotero_item_id == "ABCD1234"
        assert candidate.url == "https://doi.org/10.1038/nature14539"
        assert candidate.arxiv_id is None
        assert candidate.semantic_scholar_id is None

    def test_with_arxiv_extra(self):
        """测试从 extra 字段提取 arXiv ID"""
        raw = {
            "key": "XYZ789",
            "data": {
                "title": "Transformer Architecture",
                "creators": [{"creatorType": "author", "lastName": "Vaswani"}],
                "extra": "arXiv:1706.03762\nCitation: 50000",
            },
        }

        candidate = normalize_zotero_paper(raw)

        assert candidate.source == "zotero"
        assert candidate.arxiv_id == "1706.03762"

    def test_with_local_pdf(self):
        """测试本地 PDF 路径"""
        raw = {
            "key": "PDF123",
            "data": {
                "title": "Local Paper",
            },
            "links": {
                "attachment": {
                    "path": "/path/to/local/paper.pdf",
                }
            },
        }

        candidate = normalize_zotero_paper(raw)

        assert candidate.source == "zotero"
        assert candidate.local_pdf_path == "/path/to/local/paper.pdf"

    def test_minimal_paper(self):
        """测试最小必需字段"""
        raw = {
            "key": "MIN001",
            "data": {
                "title": "Minimal Zotero Paper",
            },
        }

        candidate = normalize_zotero_paper(raw)

        assert candidate.source == "zotero"
        assert candidate.title == "Minimal Zotero Paper"
        assert candidate.zotero_item_id == "MIN001"
        assert candidate.authors == []
        assert candidate.year is None
        assert candidate.venue is None

    def test_year_parsing_variations(self):
        """测试多种年份格式"""
        test_cases = [
            ("2024", 2024),
            ("2024-03-15", 2024),
            ("March 2024", 2024),
            ("2024/03/15", 2024),
            ("invalid", None),
            ("", None),
        ]

        for date_str, expected_year in test_cases:
            raw = {
                "key": "TEST",
                "data": {
                    "title": "Test",
                    "date": date_str,
                },
            }
            candidate = normalize_zotero_paper(raw)
            assert candidate.year == expected_year, f"Failed for date: {date_str}"


class TestDeduplication:
    """测试去重逻辑"""

    def test_dedupe_by_doi(self):
        """测试 DOI 优先去重"""
        candidates = [
            PaperCandidate(
                paper_id="ss1",
                source="semantic_scholar",
                title="Paper A",
                doi="10.1234/abc",
                semantic_scholar_id="ss123",
            ),
            PaperCandidate(
                paper_id="arxiv1",
                source="arxiv",
                title="Paper A (arXiv version)",
                doi="10.1234/abc",
                arxiv_id="2401.12345",
            ),
            PaperCandidate(
                paper_id="zot1",
                source="zotero",
                title="Paper A",
                doi="10.1234/abc",
                zotero_item_id="ZOT123",
            ),
        ]

        result = deduplicate_candidates(candidates)

        # 应该只保留一篇，优先保留 Zotero（seed paper）
        assert len(result) == 1
        assert result[0].source == "zotero"
        assert result[0].doi == "10.1234/abc"

    def test_dedupe_by_arxiv_id(self):
        """测试无 DOI 时用 arXiv ID 去重"""
        candidates = [
            PaperCandidate(
                paper_id="ss1",
                source="semantic_scholar",
                title="Attention Paper",
                arxiv_id="1706.03762",
                semantic_scholar_id="ss123",
            ),
            PaperCandidate(
                paper_id="arxiv1",
                source="arxiv",
                title="Attention Is All You Need",
                arxiv_id="1706.03762",
            ),
        ]

        result = deduplicate_candidates(candidates)

        assert len(result) == 1
        assert result[0].arxiv_id == "1706.03762"

    def test_dedupe_by_semantic_scholar_id(self):
        """测试用 Semantic Scholar ID 去重"""
        candidates = [
            PaperCandidate(
                paper_id="ss1",
                source="semantic_scholar",
                title="Paper B",
                semantic_scholar_id="ss456",
            ),
            PaperCandidate(
                paper_id="ss2",
                source="semantic_scholar",
                title="Paper B Duplicate",
                semantic_scholar_id="ss456",
            ),
        ]

        result = deduplicate_candidates(candidates)

        assert len(result) == 1
        assert result[0].semantic_scholar_id == "ss456"

    def test_dedupe_by_normalized_title(self):
        """测试用标准化标题去重"""
        candidates = [
            PaperCandidate(
                paper_id="p1",
                source="semantic_scholar",
                title="  Attention  Is All You Need!  ",
            ),
            PaperCandidate(
                paper_id="p2",
                source="arxiv",
                title="Attention is all you need",
            ),
            PaperCandidate(
                paper_id="p3",
                source="zotero",
                title="ATTENTION IS ALL YOU NEED.",
            ),
        ]

        result = deduplicate_candidates(candidates)

        # 应该只保留一篇
        assert len(result) == 1

    def test_priority_zotero_over_others(self):
        """测试 Zotero seed paper 优先级最高"""
        candidates = [
            PaperCandidate(
                paper_id="ss1",
                source="semantic_scholar",
                title="Paper C",
                doi="10.1234/xyz",
                citation_count=100,
            ),
            PaperCandidate(
                paper_id="zot1",
                source="zotero",
                title="Paper C",
                doi="10.1234/xyz",
                local_pdf_path="/local/paper.pdf",
            ),
        ]

        result = deduplicate_candidates(candidates)

        assert len(result) == 1
        assert result[0].source == "zotero"
        assert result[0].local_pdf_path == "/local/paper.pdf"
        # 应该合并 citation_count
        assert result[0].citation_count == 100

    def test_merge_metadata_on_dedupe(self):
        """测试去重时合并元数据"""
        candidates = [
            PaperCandidate(
                paper_id="ss1",
                source="semantic_scholar",
                title="Paper D",
                doi="10.1234/merge",
                semantic_scholar_id="ss789",
                citation_count=500,
                url="https://semanticscholar.org/paper/ss789",
            ),
            PaperCandidate(
                paper_id="arxiv1",
                source="arxiv",
                title="Paper D",
                doi="10.1234/merge",
                arxiv_id="2402.12345",
                pdf_url="https://arxiv.org/pdf/2402.12345.pdf",
            ),
        ]

        result = deduplicate_candidates(candidates)

        assert len(result) == 1
        merged = result[0]
        # 应该合并所有 ID
        assert merged.semantic_scholar_id == "ss789"
        assert merged.arxiv_id == "2402.12345"
        assert merged.doi == "10.1234/merge"
        # 应该保留 citation_count
        assert merged.citation_count == 500
        # 应该保留 pdf_url
        assert merged.pdf_url == "https://arxiv.org/pdf/2402.12345.pdf"

    def test_no_duplicates(self):
        """测试无重复时保留所有候选"""
        candidates = [
            PaperCandidate(
                paper_id="p1",
                source="semantic_scholar",
                title="Unique Paper 1",
                doi="10.1111/aaa",
            ),
            PaperCandidate(
                paper_id="p2",
                source="arxiv",
                title="Unique Paper 2",
                arxiv_id="2401.11111",
            ),
            PaperCandidate(
                paper_id="p3",
                source="zotero",
                title="Unique Paper 3",
                zotero_item_id="ZOT999",
            ),
        ]

        result = deduplicate_candidates(candidates)

        assert len(result) == 3

    def test_empty_list(self):
        """测试空列表"""
        result = deduplicate_candidates([])
        assert result == []

    def test_title_normalization_edge_cases(self):
        """测试标题标准化边界情况"""
        candidates = [
            PaperCandidate(
                paper_id="p1",
                source="semantic_scholar",
                title="A  B    C",  # 多余空格
            ),
            PaperCandidate(
                paper_id="p2",
                source="arxiv",
                title="a b c!!!",  # 标点符号
            ),
        ]

        result = deduplicate_candidates(candidates)
        assert len(result) == 1
