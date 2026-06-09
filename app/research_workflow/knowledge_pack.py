from __future__ import annotations

import json
import re
from pathlib import Path

from app.research_workflow.schemas import ResearchRun, ResearchRunArtifact


def slugify_run_name(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "research-run"


def create_knowledge_pack_skeleton(
    run: ResearchRun,
    vault_root: str | Path,
) -> ResearchRun:
    output_dir = _output_dir(run, vault_root)
    papers_dir = output_dir / "papers"
    assets_dir = output_dir / "assets"

    papers_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "00 Run Summary.md"
    trace_path = assets_dir / "trace.json"
    tool_calls_path = assets_dir / "tool-calls.jsonl"

    _write_if_missing(summary_path, _render_summary(run))
    _write_if_missing(
        trace_path,
        json.dumps(_trace_payload(run), ensure_ascii=False, indent=2),
    )
    _write_if_missing(tool_calls_path, "")

    return run.model_copy(
        update={
            "output_dir": str(output_dir),
            "artifacts": _merge_skeleton_artifacts(
                run,
                [
                    ResearchRunArtifact(
                        label="Knowledge Pack",
                        path=str(output_dir),
                        kind="directory",
                    ),
                    ResearchRunArtifact(
                        label="Run Summary",
                        path=str(summary_path),
                        kind="markdown",
                    ),
                    ResearchRunArtifact(
                        label="Trace",
                        path=str(trace_path),
                        kind="json",
                    ),
                    ResearchRunArtifact(
                        label="Tool Calls",
                        path=str(tool_calls_path),
                        kind="jsonl",
                    ),
                ],
            ),
        }
    )


def _output_dir(run: ResearchRun, vault_root: str | Path) -> Path:
    run_slug = slugify_run_name(run.run_id.replace("_", "-"))
    collection_slug = slugify_run_name(run.collection_name)
    return Path(vault_root) / "ResearchAgent" / "Runs" / f"{run_slug}-{collection_slug}"


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _merge_skeleton_artifacts(
    run: ResearchRun,
    skeleton_artifacts: list[ResearchRunArtifact],
) -> list[ResearchRunArtifact]:
    skeleton_by_label = {
        artifact.label: artifact
        for artifact in skeleton_artifacts
    }
    merged = [
        skeleton_by_label.get(artifact.label, artifact)
        for artifact in run.artifacts
        if artifact.label not in skeleton_by_label
    ]
    merged.extend(skeleton_artifacts)
    return merged


def _render_summary(run: ResearchRun) -> str:
    lines = [
        f"# Research Run: {run.collection_name}",
        "",
        f"- Run ID: {run.run_id}",
        f"- Collection ID: {run.collection_id}",
        f"- Collection Name: {run.collection_name}",
        f"- Goal: {run.goal}",
        f"- Status: {run.status}",
        f"- Max Papers: {run.options.max_papers}",
        "",
        "## Steps",
        "",
    ]
    lines.extend(f"- {step.agent}: {step.status}" for step in run.steps)
    lines.extend(
        [
            "",
            "## Skeleton",
            "",
            "This knowledge pack skeleton was initialized without LLM or external tool calls.",
            "",
        ]
    )
    return "\n".join(lines)


def _trace_payload(run: ResearchRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "collection_id": run.collection_id,
        "collection_name": run.collection_name,
        "goal": run.goal,
        "status": run.status,
        "steps": [step.model_dump(mode="json") for step in run.steps],
    }
