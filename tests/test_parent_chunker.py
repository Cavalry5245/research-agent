"""
测试 parent_chunker 模块。
"""

import pytest

from app.schemas import DocumentElement, ParentDocument
from app.services.parent_chunker import build_parent_documents


class TestBuildParentDocuments:
    """测试 build_parent_documents 函数。"""

    def test_empty_elements(self):
        """测试空元素列表。"""
        result = build_parent_documents(
            elements=[],
            paper_id="paper_001",
            paper_title="Test Paper",
        )
        assert result == []

    def test_abstract_independent_parent(self):
        """测试 Abstract 独立父文档。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="abstract",
                text="This is the abstract content.",
                page_number=1,
                bbox=(0.0, 0.0, 100.0, 50.0),
                section_path="Abstract",
                order_index=0,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.parent_id == "paper_001_parent_0001"
        assert parent.section_path == "Abstract"
        assert parent.element_type == "abstract"
        assert parent.content == "This is the abstract content."
        assert parent.page_range == "1"
        assert len(parent.element_ids) == 1
        assert parent.element_ids[0] == "elem_001"
        assert len(parent.bbox_refs) == 1

    def test_table_independent_parent(self):
        """测试表格独立父文档。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="table",
                text="Table 1: Results",
                page_number=3,
                bbox=(0.0, 0.0, 200.0, 100.0),
                section_path="Experiments/Results",
                order_index=10,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.element_type == "table"
        assert parent.content == "Table 1: Results"
        assert parent.page_range == "3"

    def test_references_filtered(self):
        """测试 References 元素被过滤。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Main content",
                page_number=1,
                section_path="Introduction",
                order_index=0,
                metadata={},
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="reference",
                text="[1] Reference citation",
                page_number=10,
                section_path="References",
                order_index=100,
                metadata={"in_references": True},
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        # References 元素应该被过滤
        assert len(parents) == 1
        parent = parents[0]
        assert parent.section_path == "Introduction"
        assert "Reference citation" not in parent.content
        assert len(parent.element_ids) == 1
        assert parent.element_ids[0] == "elem_001"

    def test_main_section_parent(self):
        """测试主章节（一级标题）独立父文档。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="Introduction",
                page_number=1,
                section_path="Introduction",
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="First paragraph.",
                page_number=1,
                section_path="Introduction",
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="paragraph",
                text="Second paragraph.",
                page_number=2,
                section_path="Introduction",
                order_index=2,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.section_path == "Introduction"
        assert parent.element_type == "section"
        assert "Introduction" in parent.content
        assert "First paragraph." in parent.content
        assert "Second paragraph." in parent.content
        assert parent.page_range == "1-2"
        assert len(parent.element_ids) == 3

    def test_subsection_over_2000_chars(self):
        """测试二级章节超过 2000 字符时独立父文档。"""
        long_text = "A" * 2100  # 超过 2000 字符

        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text=long_text,
                page_number=3,
                section_path="Methods/Experimental Setup",
                order_index=10,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.section_path == "Methods/Experimental Setup"
        assert parent.element_type == "section"
        assert len(parent.content) > 2000

    def test_subsection_under_2000_chars_merged(self):
        """测试二级章节不足 2000 字符时归属行为。"""
        elements = [
            # 主章节
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="heading",
                text="Methods",
                page_number=2,
                section_path="Methods",
                order_index=5,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Methods introduction.",
                page_number=2,
                section_path="Methods",
                order_index=6,
            ),
            # 二级章节（不足 2000 字符）
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="heading",
                text="Experimental Setup",
                page_number=2,
                section_path="Methods/Experimental Setup",
                order_index=7,
            ),
            DocumentElement(
                element_id="elem_004",
                paper_id="paper_001",
                type="paragraph",
                text="Setup description.",
                page_number=2,
                section_path="Methods/Experimental Setup",
                order_index=8,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        # 主章节应该独立
        # 二级章节不足 2000 字符，应该合并到主章节或创建 mixed
        assert len(parents) >= 1

        # 找到 Methods 父文档
        methods_parent = next((p for p in parents if p.section_path == "Methods"), None)
        assert methods_parent is not None
        assert "Methods introduction." in methods_parent.content

        # 二级章节可能合并或独立为 mixed
        if len(parents) == 1:
            # 合并到 Methods
            assert "Setup description." in methods_parent.content
        else:
            # 独立为 mixed（因为没有找到父章节父文档）
            subsection_parent = next(
                (p for p in parents if p.section_path == "Methods/Experimental Setup"),
                None
            )
            assert subsection_parent is not None
            assert subsection_parent.element_type == "mixed"

    def test_page_range_calculation(self):
        """测试 page_range 正确计算。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Content on page 3",
                page_number=3,
                section_path="Section1",
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Content on page 5",
                page_number=5,
                section_path="Section1",
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="paragraph",
                text="Content on page 4",
                page_number=4,
                section_path="Section1",
                order_index=2,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.page_range == "3-5"  # min=3, max=5

    def test_single_page_range(self):
        """测试单页 page_range。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Content on page 2",
                page_number=2,
                section_path="Section1",
                order_index=0,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.page_range == "2"

    def test_no_bbox_refs(self):
        """测试元素没有 bbox 时的处理。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Content without bbox",
                page_number=1,
                bbox=None,
                section_path="Section1",
                order_index=0,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.page_range == "1"
        assert len(parent.bbox_refs) == 0  # No bbox, so no bbox_refs

    def test_bbox_refs_collection(self):
        """测试 bbox_refs 正确收集。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Content 1",
                page_number=1,
                bbox=(10.0, 20.0, 100.0, 50.0),
                section_path="Section1",
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Content 2",
                page_number=2,
                bbox=(15.0, 25.0, 105.0, 55.0),
                section_path="Section1",
                order_index=1,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert len(parent.bbox_refs) == 2
        assert parent.bbox_refs[0] == (1, (10.0, 20.0, 100.0, 50.0))
        assert parent.bbox_refs[1] == (2, (15.0, 25.0, 105.0, 55.0))

    def test_mixed_element_types(self):
        """测试混合元素类型构建父文档。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="abstract",
                text="Abstract text",
                page_number=1,
                section_path="Abstract",
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="heading",
                text="Introduction",
                page_number=1,
                section_path="Introduction",
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="paragraph",
                text="Intro paragraph",
                page_number=1,
                section_path="Introduction",
                order_index=2,
            ),
            DocumentElement(
                element_id="elem_004",
                paper_id="paper_001",
                type="table",
                text="Table data",
                page_number=2,
                section_path="Results",
                order_index=10,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        # Abstract(1) + Introduction section(1) + Table(1) = 3
        assert len(parents) == 3

        # 验证 abstract
        abstract = next(p for p in parents if p.element_type == "abstract")
        assert abstract.content == "Abstract text"

        # 验证 section
        section = next(p for p in parents if p.element_type == "section")
        assert "Introduction" in section.content
        assert "Intro paragraph" in section.content

        # 验证 table
        table = next(p for p in parents if p.element_type == "table")
        assert table.content == "Table data"

    def test_multiple_sections_ordering(self):
        """测试多个章节按顺序构建父文档。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Intro content",
                page_number=1,
                section_path="Introduction",
                order_index=0,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="paragraph",
                text="Methods content",
                page_number=2,
                section_path="Methods",
                order_index=1,
            ),
            DocumentElement(
                element_id="elem_003",
                paper_id="paper_001",
                type="paragraph",
                text="Results content",
                page_number=3,
                section_path="Results",
                order_index=2,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 3
        # 顺序应与元素顺序一致
        assert parents[0].section_path == "Introduction"
        assert parents[1].section_path == "Methods"
        assert parents[2].section_path == "Results"

    def test_all_elements_filtered_returns_empty(self):
        """测试所有元素都被过滤时返回空列表。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="reference",
                text="[1] Reference",
                page_number=10,
                section_path="References",
                order_index=100,
                metadata={"in_references": True},
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert parents == []

    def test_figure_caption_in_section(self):
        """测试图注归属到所在章节父文档。"""
        elements = [
            DocumentElement(
                element_id="elem_001",
                paper_id="paper_001",
                type="paragraph",
                text="Section content",
                page_number=3,
                section_path="Results",
                order_index=10,
            ),
            DocumentElement(
                element_id="elem_002",
                paper_id="paper_001",
                type="figure_caption",
                text="Figure 1: Results visualization",
                page_number=3,
                section_path="Results",
                order_index=11,
            ),
        ]

        parents = build_parent_documents(
            elements=elements,
            paper_id="paper_001",
            paper_title="Test Paper",
        )

        assert len(parents) == 1
        parent = parents[0]
        assert parent.section_path == "Results"
        assert "Section content" in parent.content
        assert "Figure 1: Results visualization" in parent.content
        assert len(parent.element_ids) == 2
