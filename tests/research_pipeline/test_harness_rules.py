"""
Test Harness Agent - Rule-First Verification

验证 Harness 对报告 claims 的校验规则。
"""

import pytest

from app.research_pipeline.agents.harness import HarnessAgent
from app.research_pipeline.schemas import PaperCard


class TestClaimExtraction:
    """测试从报告中提取 claims"""

    def test_extract_method_claims_with_citations(self):
        """提取带引用的方法声明"""
        report = """## 2. Methodology Landscape

该领域主要使用 Transformer 架构 [CITE:paper_001] 和注意力机制 [CITE:paper_002]。
"""
        harness = HarnessAgent()
        claims = harness.execute(report, [], [])

        # Should extract at least one method claim
        method_claims = [c for c in claims if c.claim_type == "method"]
        assert len(method_claims) >= 1

        # First claim should have citations
        claim = method_claims[0]
        assert len(claim.citation_ids) >= 1
        assert "paper_001" in claim.citation_ids or "paper_002" in claim.citation_ids

    def test_extract_dataset_claims_with_citations(self):
        """提取数据集声明"""
        report = """## 3. Dataset And Metric Comparison

主要使用 ImageNet [CITE:paper_003] 和 COCO [CITE:paper_004] 数据集。
"""
        harness = HarnessAgent()
        claims = harness.execute(report, [], [])

        dataset_claims = [c for c in claims if c.claim_type == "dataset"]
        assert len(dataset_claims) >= 1
        assert any("paper_003" in c.citation_ids for c in dataset_claims)

    def test_extract_result_claims_with_numbers(self):
        """提取包含数字的结果声明"""
        report = """## 4. SOTA And Key Results

模型在 ImageNet 上达到了 85.3% 的准确率 [CITE:paper_005]。
"""
        harness = HarnessAgent()
        claims = harness.execute(report, [], [])

        result_claims = [c for c in claims if c.claim_type == "result"]
        assert len(result_claims) >= 1

        # Claim should contain numeric value
        claim = result_claims[0]
        assert "85.3" in claim.claim_text or "85.3%" in claim.claim_text


class TestUnverifiedClaims:
    """测试无引用的 claims 标记为 unverified"""

    def test_claim_without_citation_is_unverified(self):
        """没有引用的 claim 应该标记为 unverified"""
        report = """## 2. Methodology Landscape

该领域主要使用深度学习方法。
"""
        harness = HarnessAgent()
        claims = harness.execute(report, [], [])

        # Should extract claim without citation
        assert len(claims) >= 1
        claim = claims[0]
        assert claim.verification_status == "unverified"
        assert "没有引用" in claim.verification_reason or "无引用" in claim.verification_reason

    def test_claim_with_invalid_citation_is_unverified(self):
        """引用的 paper_id 不在 PaperCards 中，应标记为 unverified"""
        report = """## 2. Methodology Landscape

使用 Transformer 架构 [CITE:paper_999]。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="pdf",
                title="Valid Paper",
                bibliographic_metadata={},
            )
        ]

        harness = HarnessAgent()
        claims = harness.execute(report, paper_cards, [])

        # Claim should be unverified because paper_999 not in cards
        assert len(claims) >= 1
        claim = claims[0]
        assert claim.verification_status == "unverified"
        assert "paper_999" in claim.verification_reason


class TestNumericTraceMissing:
    """测试数字型 claim 缺少 evidence 时标记为 numeric_trace_missing"""

    def test_numeric_claim_without_evidence_is_numeric_trace_missing(self):
        """包含数字的 result claim 但没有对应 evidence"""
        report = """## 4. SOTA And Key Results

模型达到 95.2% 准确率 [CITE:paper_001]。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="pdf",
                title="Test Paper",
                bibliographic_metadata={},
            )
        ]
        evidence = []  # No evidence provided

        harness = HarnessAgent()
        claims = harness.execute(report, paper_cards, evidence)

        result_claims = [c for c in claims if c.claim_type == "result"]
        assert len(result_claims) >= 1

        claim = result_claims[0]
        assert claim.verification_status == "numeric_trace_missing"
        assert "数字" in claim.verification_reason or "evidence" in claim.verification_reason

    def test_numeric_claim_with_evidence_is_supported(self):
        """包含数字的 result claim 且有对应 evidence"""
        report = """## 4. SOTA And Key Results

模型达到 95.2% 准确率 [CITE:paper_001]。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="pdf",
                title="Test Paper",
                bibliographic_metadata={},
            )
        ]
        evidence = [
            {
                "paper_id": "paper_001",
                "claim": "accuracy 95.2%",
                "evidence_text": "Our model achieves 95.2% accuracy on ImageNet.",
            }
        ]

        harness = HarnessAgent()
        claims = harness.execute(report, paper_cards, evidence)

        result_claims = [c for c in claims if c.claim_type == "result"]
        assert len(result_claims) >= 1

        claim = result_claims[0]
        assert claim.verification_status == "supported"
        assert len(claim.evidence_ids) >= 1


class TestAbstractOnlyWeakStatus:
    """测试 abstract-only 的 evidence 最高只能是 weak"""

    def test_abstract_only_evidence_max_weak_status(self):
        """abstract-only 的 PaperCard 提供的 evidence 最多 weak"""
        report = """## 2. Methodology Landscape

使用 BERT 模型 [CITE:paper_001]。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="abstract_only",  # Abstract only
                title="Test Paper",
                bibliographic_metadata={},
            )
        ]
        evidence = [
            {
                "paper_id": "paper_001",
                "claim": "uses BERT",
                "evidence_text": "We use BERT model.",
            }
        ]

        harness = HarnessAgent()
        claims = harness.execute(report, paper_cards, evidence)

        method_claims = [c for c in claims if c.claim_type == "method"]
        assert len(method_claims) >= 1

        claim = method_claims[0]
        # Should be weak because paper_001 is abstract_only
        assert claim.verification_status == "weak"
        assert "abstract" in claim.verification_reason.lower()

    def test_pdf_evidence_can_be_supported(self):
        """PDF 模式的 evidence 可以是 supported"""
        report = """## 2. Methodology Landscape

使用 BERT 模型 [CITE:paper_001]。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="pdf",  # Full PDF
                title="Test Paper",
                bibliographic_metadata={},
            )
        ]
        evidence = [
            {
                "paper_id": "paper_001",
                "claim": "uses BERT",
                "evidence_text": "We use BERT model.",
            }
        ]

        harness = HarnessAgent()
        claims = harness.execute(report, paper_cards, evidence)

        method_claims = [c for c in claims if c.claim_type == "method"]
        assert len(method_claims) >= 1

        claim = method_claims[0]
        # Can be supported because paper_001 is pdf mode
        assert claim.verification_status == "supported"


class TestReportNotMutated:
    """测试 Harness 不修改原始报告内容"""

    def test_report_content_unchanged(self):
        """Harness 不应该修改报告原文"""
        original_report = """## 1. Research Question

这是一个测试问题。

## 2. Methodology Landscape

使用深度学习 [CITE:paper_001]。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="pdf",
                title="Test Paper",
                bibliographic_metadata={},
            )
        ]

        harness = HarnessAgent()
        claims = harness.execute(original_report, paper_cards, [])

        # Report should not be modified
        # (Harness only returns claims, doesn't modify report)
        assert len(claims) >= 1  # Claims extracted
        # Original report is not modified (no return value for report)


class TestHarnessSummary:
    """测试 Harness summary 统计"""

    def test_summary_aggregates_by_status(self):
        """Harness summary 按 verification_status 聚合"""
        report = """## 2. Methodology Landscape

使用 Transformer 架构 [CITE:paper_001]。
另一种方法是基于规则的系统，但没有引用支持。
达到 95% 准确率 [CITE:paper_002]。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="pdf",
                title="Paper 1",
                bibliographic_metadata={},
            ),
            PaperCard(
                paper_id="paper_002",
                status="completed",
                extraction_mode="abstract_only",
                title="Paper 2",
                bibliographic_metadata={},
            ),
        ]
        evidence = []  # No evidence for numeric claim

        harness = HarnessAgent()
        claims = harness.execute(report, paper_cards, evidence)

        # Should have at least 3 claims
        assert len(claims) >= 3

        # Should have different status types
        statuses = {c.verification_status for c in claims}
        assert len(statuses) >= 2  # At least 2 different statuses

        # Check summary can be computed
        summary = harness.get_summary(claims)
        assert "unverified" in summary or "supported" in summary or "weak" in summary
        assert sum(summary.values()) == len(claims)


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_report_returns_empty_claims(self):
        """空报告返回空 claims 列表"""
        harness = HarnessAgent()
        claims = harness.execute("", [], [])
        assert claims == []

    def test_report_with_no_claims_returns_empty(self):
        """没有可提取 claims 的报告返回空列表"""
        report = """# Title

Just some text without claims or citations.
"""
        harness = HarnessAgent()
        claims = harness.execute(report, [], [])
        assert claims == []

    def test_multiple_citations_in_one_claim(self):
        """一个 claim 包含多个引用"""
        report = """## 2. Methodology Landscape

使用 Transformer [CITE:paper_001] 和 BERT [CITE:paper_002] 架构。
"""
        paper_cards = [
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="pdf",
                title="Paper 1",
                bibliographic_metadata={},
            ),
            PaperCard(
                paper_id="paper_002",
                status="completed",
                extraction_mode="pdf",
                title="Paper 2",
                bibliographic_metadata={},
            ),
        ]

        harness = HarnessAgent()
        claims = harness.execute(report, paper_cards, [])

        assert len(claims) >= 1
        claim = claims[0]
        assert len(claim.citation_ids) == 2
        assert "paper_001" in claim.citation_ids
        assert "paper_002" in claim.citation_ids
