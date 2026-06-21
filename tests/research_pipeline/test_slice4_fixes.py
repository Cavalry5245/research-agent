"""
Slice 4 修复验证测试

验证两个关键修复：
1. Harness citation parser 支持 arXiv paper_id (带点号)
2. Synthesis skeleton fallback 使用 [CITE:paper_id] 格式
"""

import pytest

from app.research_pipeline.agents.harness import HarnessAgent
from app.research_pipeline.agents.synthesis import SynthesisAgent
from app.research_pipeline.schemas import PaperCard


class TestSlice4Fixes:
    """Slice 4 修复验证测试套件"""

    def test_harness_parses_arxiv_paper_ids_with_dots(self):
        """验证 Harness 可以解析带点号的 arXiv paper_id"""
        harness = HarnessAgent()

        # 模拟一个引用 arXiv ID 的报告
        report = """
# Research Report

## 2. Methodology Landscape

The transformer architecture [CITE:1706.03762] introduced multi-head attention.
BERT [CITE:1810.04805] achieved SOTA on many NLP tasks.
Recent work on RAG [CITE:2005.11401] combines retrieval with generation.

## 4. SOTA And Key Results

GPT-3 [CITE:2005.14165] achieved 85.3% accuracy on SuperGLUE.
T5 [CITE:1910.10683] demonstrated transfer learning effectiveness.
"""

        # PaperCards 使用真实的 arXiv IDs
        paper_cards = [
            PaperCard(
                paper_id="1706.03762",
                status="completed",
                extraction_mode="pdf",
                title="Attention Is All You Need",
                bibliographic_metadata={"year": 2017, "authors": ["Vaswani et al."]},
                research_problem="",
                method="Transformer",
                datasets=["WMT"],
                metrics=["BLEU"],
                key_results=["28.4 BLEU on WMT 2014 En-De"],
                limitations=[],
                assumptions=[],
                future_work=[],
                claims=[],
                evidence=[],
                error=None,
            ),
            PaperCard(
                paper_id="1810.04805",
                status="completed",
                extraction_mode="pdf",
                title="BERT",
                bibliographic_metadata={"year": 2018, "authors": ["Devlin et al."]},
                research_problem="",
                method="BERT",
                datasets=["GLUE"],
                metrics=["accuracy"],
                key_results=["93.5% on MNLI"],
                limitations=[],
                assumptions=[],
                future_work=[],
                claims=[],
                evidence=[],
                error=None,
            ),
            PaperCard(
                paper_id="2005.14165",
                status="completed",
                extraction_mode="pdf",
                title="GPT-3",
                bibliographic_metadata={"year": 2020, "authors": ["Brown et al."]},
                research_problem="",
                method="GPT-3",
                datasets=["SuperGLUE"],
                metrics=["accuracy"],
                key_results=["85.3% on SuperGLUE"],
                limitations=[],
                assumptions=[],
                future_work=[],
                claims=[],
                evidence=[
                    {
                        "paper_id": "2005.14165",
                        "snippet": "GPT-3 achieved 85.3% accuracy on SuperGLUE",
                        "section": "Results",
                    }
                ],
                error=None,
            ),
        ]

        evidence = [
            {
                "paper_id": "2005.14165",
                "snippet": "GPT-3 achieved 85.3% accuracy on SuperGLUE",
                "section": "Results",
            }
        ]

        # 执行 Harness
        claims = harness.execute(report, paper_cards, evidence)

        # 验证所有 arXiv citations 都被正确解析
        method_claims = [c for c in claims if c.claim_type == "method"]
        result_claims = [c for c in claims if c.claim_type == "result"]

        # 检查 method claims 的 citations
        transformer_claim = next(
            (c for c in method_claims if "1706.03762" in c.citation_ids), None
        )
        assert transformer_claim is not None, "Transformer claim should have citation"
        assert (
            "1706.03762" in transformer_claim.citation_ids
        ), "Should parse arXiv ID with dots"
        assert (
            transformer_claim.verification_status != "unverified"
        ), "Valid arXiv citation should not be unverified"

        bert_claim = next(
            (c for c in method_claims if "1810.04805" in c.citation_ids), None
        )
        assert bert_claim is not None, "BERT claim should have citation"
        assert (
            "1810.04805" in bert_claim.citation_ids
        ), "Should parse arXiv ID with dots"

        # 检查 result claims 的 citations
        gpt3_claim = next(
            (c for c in result_claims if "2005.14165" in c.citation_ids), None
        )
        assert gpt3_claim is not None, "GPT-3 claim should have citation"
        assert (
            "2005.14165" in gpt3_claim.citation_ids
        ), "Should parse arXiv ID with dots"
        assert gpt3_claim.verification_status in [
            "supported",
            "weak",
        ], "GPT-3 claim should be supported or weak"

    def test_synthesis_skeleton_uses_cite_format(self):
        """验证 Synthesis skeleton fallback 使用 [CITE:paper_id] 格式"""
        synthesis = SynthesisAgent(db_path=":memory:", llm_client=None)  # Force skeleton mode

        paper_cards = [
            PaperCard(
                paper_id="paper_1",
                status="completed",
                extraction_mode="pdf",
                title="Test Paper 1",
                bibliographic_metadata={"year": 2023, "authors": ["Alice"]},
                research_problem="Test problem",
                method="Test method",
                datasets=["Dataset A"],
                metrics=["Accuracy"],
                key_results=["Achieved 95% accuracy"],
                limitations=["Limited to English"],
                assumptions=[],
                future_work=["Extend to other languages"],
                claims=[],
                evidence=[],
                error=None,
            ),
            PaperCard(
                paper_id="arxiv:2103.12345",
                status="completed",
                extraction_mode="abstract_only",
                title="Test Paper 2",
                bibliographic_metadata={"year": 2024, "authors": ["Bob"]},
                research_problem="Another problem",
                method="Another method",
                datasets=["Dataset B"],
                metrics=["F1"],
                key_results=["F1 score of 0.92"],
                limitations=["Requires large GPU"],
                assumptions=[],
                future_work=["Optimize memory usage"],
                claims=[],
                evidence=[],
                error=None,
            ),
        ]

        report = synthesis.execute(
            initial_plan={"normalized_question": "Test question"},
            candidate_selection_plan={},
            paper_cards=paper_cards,
            evidence=[],
        )

        # 验证 skeleton report 包含 [CITE:paper_id] 格式
        assert "[CITE:paper_1]" in report, "Skeleton should use [CITE:paper_id] format"
        assert (
            "[CITE:arxiv:2103.12345]" in report
        ), "Skeleton should support arXiv IDs with colons"

        # 验证 skeleton 在关键部分使用了 CITE 格式
        assert (
            "## 3. Dataset And Metric Comparison" in report
        ), "Should have section 3"
        assert "## 4. SOTA And Key Results" in report, "Should have section 4"
        assert "## 5. Limitations And Failure Modes" in report, "Should have section 5"
        assert "## 7. Research Gaps" in report, "Should have section 7"

        # 确保没有旧的 [paper_id] 格式（不带 CITE: 前缀）
        # 这个检查需要排除 References 部分，因为那里合法地使用 [paper_id] 作为标题
        content_sections = report.split("## 8. References")[0]
        # 在内容部分，所有的 [xxx] 应该是 [CITE:xxx] 或 markdown 元数据，不应该有裸的 [paper_id]
        import re

        # 找出所有 [xxx] 但不是 [CITE:xxx] 的模式
        bare_paper_refs = re.findall(
            r"\[(?!CITE:)(?!自动综合不可用)(paper_[^\]]+|arxiv:[^\]]+)\]",
            content_sections,
        )
        assert (
            not bare_paper_refs
        ), f"Should not have bare paper references without CITE: prefix: {bare_paper_refs}"

    def test_end_to_end_skeleton_to_harness(self):
        """端到端测试：Synthesis skeleton → Harness 能正确验证"""
        synthesis = SynthesisAgent(db_path=":memory:", llm_client=None)
        harness = HarnessAgent()

        paper_cards = [
            PaperCard(
                paper_id="1706.03762",
                status="completed",
                extraction_mode="pdf",
                title="Attention Is All You Need",
                bibliographic_metadata={"year": 2017, "authors": ["Vaswani et al."]},
                research_problem="",
                method="Transformer",
                datasets=["WMT 2014"],
                metrics=["BLEU"],
                key_results=["28.4 BLEU on WMT 2014 En-De translation"],
                limitations=["Requires large GPU memory"],
                assumptions=[],
                future_work=["Apply to other sequence tasks"],
                claims=[],
                evidence=[],
                error=None,
            )
        ]

        # 生成 skeleton report
        report = synthesis.execute(
            initial_plan={"normalized_question": "What are transformers?"},
            candidate_selection_plan={},
            paper_cards=paper_cards,
            evidence=[],
        )

        # Harness 验证
        claims = harness.execute(report, paper_cards, evidence=[])

        # 验证至少提取到了一些 claims
        assert len(claims) > 0, "Harness should extract claims from skeleton report"

        # 验证至少有一个 claim 有正确的 citation
        claims_with_valid_citations = [
            c for c in claims if "1706.03762" in c.citation_ids
        ]
        assert (
            len(claims_with_valid_citations) > 0
        ), "At least one claim should have valid arXiv citation"

        # 验证这些 claims 不是 unverified（因为 paper_id 存在于 PaperCards 中）
        for claim in claims_with_valid_citations:
            assert (
                claim.verification_status != "unverified"
            ), f"Claim with valid citation should not be unverified: {claim.claim_text}"

        summary = harness.get_summary(claims)
        # get_summary returns {status: count}, calculate total from all statuses
        total_claims = sum(summary.values())
        assert total_claims > 0, "Should have total claims"
        unverified_count = summary.get("unverified", 0)
        assert (
            unverified_count < total_claims
        ), "Not all claims should be unverified"
