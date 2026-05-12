import json
from datetime import datetime
import logging
from pathlib import Path

from app.evaluation.metrics import load_comparison_samples
from app.prompts.compare_prompt import build_compare_prompt, build_extraction_prompt
from app.schemas import (
    CompareAspect,
    CompareBatchRunResult,
    CompareBatchSampleResult,
    PaperComparisonResult,
    PaperEvidence,
    PaperStructuredSummary,
)
from app.services.llm_client import LLMClient
from app.services.pdf_parser import load_parsed_result

logger = logging.getLogger(__name__)

COMPARE_ASPECT_ORDER = [
    "research_problem",
    "method",
    "backbone",
    "dataset",
    "metrics",
    "strengths",
    "limitations",
    "scenarios",
    "key_differences",
]

COMPARE_ASPECT_TO_SUMMARY_FIELD = {
    "research_problem": "research_problem",
    "method": "method",
    "backbone": "backbone",
    "dataset": "dataset",
    "metrics": "metrics",
    "strengths": "strengths",
    "limitations": "limitations",
    "scenarios": "scenarios",
}

COMPARE_ASPECT_LABELS = {
    "research_problem": "研究问题",
    "method": "核心方法",
    "backbone": "关键模块/骨干",
    "dataset": "数据集",
    "metrics": "评价指标",
    "strengths": "主要优势",
    "limitations": "局限性",
    "scenarios": "适用场景",
    "key_differences": "关键差异",
}


def _build_paper_summary(parsed: dict) -> str:
    lines = [
        f"### {parsed.get('title', '未知')}",
        f"- paper_id: {parsed.get('paper_id', 'unknown')}",
        f"- 摘要: {parsed.get('abstract', '无')[:500]}",
    ]
    for sec in parsed.get("sections", []):
        heading = sec.get("heading", "")
        content = sec.get("content", "")[:400]
        if content:
            lines.append(f"- {heading}: {content}")
    return "\n".join(lines)


def _normalize_summary_field(value: str | None) -> str:
    if value is None:
        return "未明确说明"
    text = str(value).strip()
    return text or "未明确说明"


def _normalize_summary_evidence(
    evidence_items: list[dict],
    paper_id: str,
    paper_title: str,
) -> list[PaperEvidence]:
    normalized = []
    for item in evidence_items:
        normalized.append(
            PaperEvidence(
                paper_id=paper_id,
                paper_title=paper_title,
                section=_normalize_summary_field(item.get("section")),
                snippet=_normalize_summary_field(item.get("snippet")),
            )
        )
    return normalized


def _normalize_paper_summary(
    paper_id: str,
    paper_title: str,
    raw: dict,
) -> PaperStructuredSummary:
    return PaperStructuredSummary(
        paper_id=paper_id,
        paper_title=paper_title,
        research_problem=_normalize_summary_field(raw.get("research_problem")),
        method=_normalize_summary_field(raw.get("method")),
        backbone=_normalize_summary_field(raw.get("backbone")),
        dataset=_normalize_summary_field(raw.get("dataset")),
        metrics=_normalize_summary_field(raw.get("metrics")),
        strengths=_normalize_summary_field(raw.get("strengths")),
        limitations=_normalize_summary_field(raw.get("limitations")),
        scenarios=_normalize_summary_field(raw.get("scenarios")),
        evidence=_normalize_summary_evidence(raw.get("evidence", []), paper_id, paper_title),
    )


def _build_structured_summaries_text(summaries: dict[str, PaperStructuredSummary]) -> str:
    payload = {paper_id: summary.model_dump(mode="json") for paper_id, summary in summaries.items()}
    return "## Structured Paper Summaries\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _infer_aspect_evidence(
    aspect_name: str,
    per_paper: dict[str, str],
    summaries: dict[str, PaperStructuredSummary],
) -> list[PaperEvidence]:
    summary_field = COMPARE_ASPECT_TO_SUMMARY_FIELD.get(aspect_name)
    if summary_field is None:
        return []

    inferred: list[PaperEvidence] = []
    for paper_id, summary in summaries.items():
        aspect_value = per_paper.get(paper_id, "未明确说明")
        if aspect_value == "未明确说明":
            continue
        summary_value = getattr(summary, summary_field, "未明确说明")
        if summary_value == "未明确说明":
            continue
        inferred.extend(summary.evidence)
    return inferred


def _normalize_comparison_result(raw: dict, paper_ids: list[str], summaries: dict[str, PaperStructuredSummary]) -> PaperComparisonResult:
    aspects = []
    for item in raw.get("aspects", []):
        per_paper = {
            pid: item.get("per_paper", {}).get(pid, "未明确说明") for pid in paper_ids
        }
        evidence = [PaperEvidence(**e) for e in item.get("evidence", [])]
        if not evidence:
            evidence = _infer_aspect_evidence(item.get("name", "unknown"), per_paper, summaries)
        aspects.append(
            CompareAspect(
                name=item.get("name", "unknown"),
                summary=item.get("summary", "未明确说明"),
                key_differences=item.get("key_differences", []),
                per_paper=per_paper,
                evidence=evidence,
            )
        )

    comparison = PaperComparisonResult(
        overview=raw.get("overview", "未明确说明"),
        aspects=aspects,
        markdown="",
        structured_summaries=summaries,
    )
    comparison.markdown = _build_comparison_markdown(comparison, raw.get("paper_titles", {}), paper_ids)
    return comparison



def _build_comparison_markdown(
    comparison: PaperComparisonResult,
    paper_titles: dict[str, str],
    paper_ids: list[str],
) -> str:
    ordered_titles = [paper_titles.get(pid, pid) for pid in paper_ids]
    lines = ["# 多论文结构化对比", "", "## 总览", comparison.overview, ""]

    header = "| 维度 | " + " | ".join(ordered_titles) + " | 总结 |"
    divider = "|---|" + "|".join(["---"] * (len(ordered_titles) + 1)) + "|"
    lines.extend([header, divider])

    aspect_map = {aspect.name: aspect for aspect in comparison.aspects}
    for aspect_name in COMPARE_ASPECT_ORDER:
        aspect = aspect_map.get(aspect_name)
        if aspect is None:
            continue
        row = [COMPARE_ASPECT_LABELS.get(aspect_name, aspect_name)]
        for pid in paper_ids:
            row.append(aspect.per_paper.get(pid, "未明确说明"))
        row.append(aspect.summary)
        lines.append("| " + " | ".join(row) + " |")

    remaining_aspects = [
        aspect for aspect in comparison.aspects if aspect.name not in COMPARE_ASPECT_ORDER
    ]
    for aspect in remaining_aspects:
        row = [COMPARE_ASPECT_LABELS.get(aspect.name, aspect.name)]
        for pid in paper_ids:
            row.append(aspect.per_paper.get(pid, "未明确说明"))
        row.append(aspect.summary)
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(["", "## 关键差异", ""])
    for aspect in comparison.aspects:
        if not aspect.key_differences:
            continue
        lines.append(f"### {COMPARE_ASPECT_LABELS.get(aspect.name, aspect.name)}")
        for diff in aspect.key_differences:
            lines.append(f"- {diff}")
        lines.append("")

    lines.extend(["## 证据摘录", ""])
    for aspect in comparison.aspects:
        if not aspect.evidence:
            continue
        lines.append(f"### {COMPARE_ASPECT_LABELS.get(aspect.name, aspect.name)}")
        for evidence in aspect.evidence:
            lines.append(
                f"- [{evidence.paper_title}] {evidence.section}: {evidence.snippet}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"



def extract_paper_summaries(
    paper_ids: list[str],
    metadata_dir: str,
    llm_client: LLMClient | None = None,
) -> dict[str, PaperStructuredSummary]:
    if llm_client is None:
        llm_client = LLMClient()

    raw_papers: list[dict] = []
    paper_titles: dict[str, str] = {}
    for pid in paper_ids:
        data = load_parsed_result(pid, metadata_dir)
        paper_titles[pid] = data.get("title", pid)
        raw_papers.append(data)

    papers_text = "\n\n---\n\n".join(_build_paper_summary(data) for data in raw_papers)
    prompt = build_extraction_prompt(papers_text)
    raw_result = llm_client.generate_text(prompt)
    try:
        parsed_result = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise RuntimeError("单篇结构化抽取结果解析失败") from exc

    return {
        pid: _normalize_paper_summary(pid, paper_titles[pid], parsed_result.get(pid, {}))
        for pid in paper_ids
    }



def compare_papers(
    paper_ids: list[str],
    metadata_dir: str,
    llm_client: LLMClient | None = None,
) -> PaperComparisonResult:
    if len(paper_ids) < 2:
        raise ValueError("请选择至少 2 篇论文进行对比")
    if len(paper_ids) > 5:
        raise ValueError("最多支持 5 篇论文对比")

    if llm_client is None:
        llm_client = LLMClient()

    extracted_summaries = extract_paper_summaries(
        paper_ids,
        metadata_dir,
        llm_client=llm_client,
    )
    paper_titles = {
        pid: summary.paper_title for pid, summary in extracted_summaries.items()
    }

    papers_text = _build_structured_summaries_text(extracted_summaries)
    prompt = build_compare_prompt(papers_text)

    logger.info("Comparing %d papers", len(paper_ids))
    raw_result = llm_client.generate_text(prompt)
    try:
        parsed_result = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise RuntimeError("结构化对比结果解析失败") from exc

    parsed_result["paper_titles"] = paper_titles
    return _normalize_comparison_result(parsed_result, paper_ids, extracted_summaries)



def compare_papers_batch(
    dataset_path: str,
    metadata_dir: str,
    llm_client: LLMClient | None = None,
) -> CompareBatchRunResult:
    samples = load_comparison_samples(dataset_path)
    results: list[CompareBatchSampleResult] = []

    for sample in samples:
        comparison = compare_papers(
            paper_ids=sample.paper_ids,
            metadata_dir=metadata_dir,
            llm_client=llm_client,
        )
        results.append(
            CompareBatchSampleResult(
                sample_id=sample.sample_id,
                question=sample.question,
                paper_ids=sample.paper_ids,
                comparison=comparison,
            )
        )

    return CompareBatchRunResult(
        dataset_path=str(Path(dataset_path)),
        total_samples=len(results),
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        results=results,
    )



def save_compare_batch_result(result: CompareBatchRunResult, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return str(path)



def save_compare_result(markdown: str, note_dir: str) -> str:
    import os

    os.makedirs(note_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(note_dir, f"compare_{ts}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)
    return filepath
