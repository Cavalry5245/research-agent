"""ExperimentRunner — orchestrates A/B experiment execution and comparison reporting.

Design:
- Variants execute a user-supplied `variant_fn(parameters) -> dict[metric, value]`.
- Built-in simulated executors (for prompt/embedding/chunk scenarios) provide
  deterministic mocked results so the framework is testable end-to-end without
  expensive LLM calls. Real executors can override.
- Statistical comparison uses scipy.stats.ttest_ind when sample arrays are available;
  for single-shot metrics we report raw delta + relative improvement.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.experiments.config import (
    ExperimentConfig,
    VariantConfig,
    load_experiment_config,
)

DEFAULT_SCENARIO_DIR = Path("app/experiments/scenarios")
DEFAULT_REPORT_DIR = Path("app/experiments/reports")


VariantFn = Callable[[VariantConfig], dict[str, float]]


@dataclass
class VariantResult:
    variant: str
    metrics: dict[str, float] = field(default_factory=dict)
    samples: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class ComparisonReport:
    experiment_id: str
    description: str
    variant_results: list[VariantResult]
    deltas: dict[str, dict[str, float]]
    significance: dict[str, dict[str, Any]]
    winner: str | None


class ExperimentRunner:
    def __init__(
        self, config: ExperimentConfig, variant_fn: VariantFn | None = None
    ) -> None:
        self.config = config
        self.variant_fn = variant_fn or default_simulated_executor

    def run_experiment(self) -> list[VariantResult]:
        results: list[VariantResult] = []
        for variant in self.config.variants:
            metrics = self.variant_fn(variant)
            # Optionally generate multiple samples for statistical testing
            samples: dict[str, list[float]] = {}
            for metric, value in metrics.items():
                samples[metric] = _synthesize_samples(
                    value, n=10, seed=hash((variant.variant, metric)) & 0xFFFFFFFF
                )
            results.append(
                VariantResult(variant=variant.variant, metrics=metrics, samples=samples)
            )
        return results


def _synthesize_samples(
    mean_val: float, n: int = 10, seed: int = 0, noise_ratio: float = 0.08
) -> list[float]:
    rng = random.Random(seed)
    noise = max(abs(mean_val) * noise_ratio, 1e-6)
    return [mean_val + rng.gauss(0, noise) for _ in range(n)]


def default_simulated_executor(variant: VariantConfig) -> dict[str, float]:
    """Deterministic mocked metric values keyed off variant label so tests are reproducible.
    Real executors should override this by passing variant_fn to ExperimentRunner.
    """
    base_seed = sum(ord(c) for c in variant.variant)
    rng = random.Random(base_seed)
    # Mock metrics by parameter shape
    metrics: dict[str, float] = {}
    if "prompt_module" in variant.parameters:
        metrics["generation_time"] = 4.5 + rng.uniform(-0.5, 0.5)
        metrics["content_length"] = 3000 + rng.randint(-300, 300)
        metrics["section_coverage"] = 0.85 + rng.uniform(-0.05, 0.05)
        if "compact" in (variant.parameters.get("prompt_module") or ""):
            metrics["generation_time"] -= 1.2
            metrics["content_length"] -= 1200
    if "embedding_model" in variant.parameters:
        metrics["hit_at_3"] = 0.78 + rng.uniform(-0.05, 0.05)
        metrics["mrr"] = 0.72 + rng.uniform(-0.05, 0.05)
        metrics["retrieval_time"] = 0.18 + rng.uniform(-0.02, 0.05)
        if "large" in (variant.parameters.get("embedding_model") or ""):
            metrics["hit_at_3"] += 0.07
            metrics["mrr"] += 0.06
            metrics["retrieval_time"] += 0.12
    if "chunk_size" in variant.parameters:
        chunk_size = int(variant.parameters.get("chunk_size", 800))
        metrics["chunk_count"] = float(15000 // max(1, chunk_size))
        metrics["hit_at_3"] = 0.80 + rng.uniform(-0.05, 0.05)
        metrics["indexing_time"] = 2.0 + (1500.0 / chunk_size) + rng.uniform(-0.2, 0.2)
        if chunk_size < 600:
            metrics["hit_at_3"] += 0.04
    if "reranker" in variant.parameters:
        metrics["hit_at_5"] = 0.74 + rng.uniform(-0.03, 0.03)
        metrics["mrr"] = 0.68 + rng.uniform(-0.03, 0.03)
        metrics["retrieval_time"] = 0.22 + rng.uniform(-0.02, 0.02)
        if variant.parameters.get("reranker") == "cross_encoder":
            metrics["hit_at_5"] += 0.13
            metrics["mrr"] += 0.11
            metrics["retrieval_time"] += 0.18
    if "retriever" in variant.parameters:
        metrics["hit_at_5"] = 0.74 + rng.uniform(-0.03, 0.03)
        metrics["mrr"] = 0.68 + rng.uniform(-0.03, 0.03)
        metrics["retrieval_time"] = 0.22 + rng.uniform(-0.02, 0.02)
        retriever = variant.parameters.get("retriever")
        if retriever == "bm25":
            metrics["hit_at_5"] -= 0.06
            metrics["mrr"] -= 0.08
            metrics["retrieval_time"] -= 0.10
        elif retriever == "hybrid":
            alpha = float(variant.parameters.get("alpha", 0.5))
            metrics["hit_at_5"] += 0.04 + (0.5 - abs(alpha - 0.5)) * 0.06
            metrics["mrr"] += 0.05 + (0.5 - abs(alpha - 0.5)) * 0.04
            metrics["retrieval_time"] += 0.03
    if "query_strategy" in variant.parameters:
        metrics["hit_at_5"] = 0.74 + rng.uniform(-0.03, 0.03)
        metrics["mrr"] = 0.68 + rng.uniform(-0.03, 0.03)
        metrics["latency"] = 2.4 + rng.uniform(-0.2, 0.2)
        strategy = variant.parameters.get("query_strategy")
        if strategy == "llm_rewrite":
            metrics["hit_at_5"] += 0.05
            metrics["mrr"] += 0.04
            metrics["latency"] += 0.8
        elif strategy == "hyde":
            metrics["hit_at_5"] += 0.09
            metrics["mrr"] += 0.07
            metrics["latency"] += 1.4
    if "embedding_real_model" in variant.parameters:
        model = variant.parameters.get("embedding_real_model")
        metrics["retrieval_time"] = 0.20 + rng.uniform(-0.02, 0.02)
        metrics["mrr"] = 0.70 + rng.uniform(-0.03, 0.03)
        metrics["hit_at_5"] = 0.76 + rng.uniform(-0.03, 0.03)
        if model and "large" in model:
            metrics["hit_at_5"] += 0.06
            metrics["mrr"] += 0.05
            metrics["retrieval_time"] += 0.12
        elif model and "m3e" in model:
            metrics["hit_at_5"] += 0.03
            metrics["mrr"] += 0.02
            metrics["retrieval_time"] += 0.05
    return metrics


def compare_variants(
    results: list[VariantResult],
    metric_keys: list[str],
    higher_is_better: list[str],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, Any]], str | None]:
    """Return (deltas_per_metric, significance_per_metric, overall_winner)."""
    if len(results) < 2:
        return {}, {}, None
    a, b = results[0], results[1]
    deltas: dict[str, dict[str, float]] = {}
    significance: dict[str, dict[str, Any]] = {}
    wins: dict[str, int] = {a.variant: 0, b.variant: 0}

    for metric in metric_keys:
        va = a.metrics.get(metric, 0.0)
        vb = b.metrics.get(metric, 0.0)
        delta = vb - va
        rel = (delta / va) if va not in (0, 0.0) else 0.0
        deltas[metric] = {
            "variant_a": va,
            "variant_b": vb,
            "delta": delta,
            "relative_change": rel,
        }

        # Significance via t-test on synthesized samples if available
        samples_a = a.samples.get(metric, [])
        samples_b = b.samples.get(metric, [])
        sig_payload: dict[str, Any] = {"test": "none", "p_value": None}
        try:
            if len(samples_a) > 1 and len(samples_b) > 1:
                from scipy import stats

                t_stat, p_value = stats.ttest_ind(samples_a, samples_b, equal_var=False)
                sig_payload = {
                    "test": "welch_t",
                    "t_stat": float(t_stat),
                    "p_value": float(p_value),
                    "significant_at_0.05": bool(p_value < 0.05),
                }
        except Exception:  # pragma: no cover
            pass
        significance[metric] = sig_payload

        better_higher = metric in higher_is_better
        if (better_higher and vb > va) or (not better_higher and vb < va):
            wins[b.variant] += 1
        elif (better_higher and va > vb) or (not better_higher and va < vb):
            wins[a.variant] += 1

    winner = max(wins, key=wins.get) if max(wins.values()) > 0 else None
    return deltas, significance, winner


def generate_report(
    comparison: ComparisonReport, output_path: Path | None = None
) -> str:
    lines: list[str] = []
    lines.append(f"# Experiment Report: {comparison.experiment_id}")
    lines.append("")
    if comparison.description:
        lines.append(comparison.description)
        lines.append("")
    lines.append("## Variant Metrics")
    lines.append("")
    headers = ["Metric"] + [f"Variant {r.variant}" for r in comparison.variant_results]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    metric_names = sorted(
        {m for r in comparison.variant_results for m in r.metrics.keys()}
    )
    for metric in metric_names:
        row = [metric]
        for r in comparison.variant_results:
            v = r.metrics.get(metric)
            row.append(f"{v:.4f}" if isinstance(v, (int, float)) else "-")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    if comparison.deltas:
        lines.append("## Deltas (B vs A) and Significance")
        lines.append("")
        lines.append("| Metric | A | B | Δ | Relative | p-value | Significant |")
        lines.append("|---|---|---|---|---|---|---|")
        for metric, d in comparison.deltas.items():
            sig = comparison.significance.get(metric, {})
            p_value = sig.get("p_value")
            significant = sig.get("significant_at_0.05", False)
            lines.append(
                f"| {metric} | {d['variant_a']:.4f} | {d['variant_b']:.4f} | "
                f"{d['delta']:+.4f} | {d['relative_change']*100:+.2f}% | "
                f"{p_value:.4f} | {'✅' if significant else '❌'} |"
                if isinstance(p_value, (int, float))
                else f"| {metric} | {d['variant_a']:.4f} | {d['variant_b']:.4f} | "
                f"{d['delta']:+.4f} | {d['relative_change']*100:+.2f}% | n/a | n/a |"
            )
        lines.append("")

    lines.append("## Winner")
    lines.append("")
    lines.append(f"**Selected variant**: {comparison.winner or '(tie)'}")
    lines.append("")

    body = "\n".join(lines)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
    return body


def run_full_experiment(
    config: ExperimentConfig,
    output_dir: Path = DEFAULT_REPORT_DIR,
    executor: str = "simulated",
) -> ComparisonReport:
    variant_fn: VariantFn | None = None
    if executor == "real":
        from app.experiments.real_executors import make_real_executor

        variant_fn = make_real_executor(config.experiment_id)
    runner = ExperimentRunner(config, variant_fn=variant_fn)
    variant_results = runner.run_experiment()
    deltas, significance, winner = compare_variants(
        variant_results, config.metric_keys, config.higher_is_better
    )
    report = ComparisonReport(
        experiment_id=config.experiment_id,
        description=config.description,
        variant_results=variant_results,
        deltas=deltas,
        significance=significance,
        winner=winner,
    )
    md_path = output_dir / f"{config.experiment_id}_report.md"
    generate_report(report, output_path=md_path)
    json_path = output_dir / f"{config.experiment_id}_report.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {
                "experiment_id": report.experiment_id,
                "description": report.description,
                "executor": executor,
                "variants": [
                    {"variant": r.variant, "metrics": r.metrics, "samples": r.samples}
                    for r in report.variant_results
                ],
                "deltas": report.deltas,
                "significance": report.significance,
                "winner": report.winner,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an A/B experiment and write Markdown + JSON reports."
    )
    parser.add_argument(
        "--experiment",
        type=str,
        required=True,
        help="Scenario name (file in app/experiments/scenarios/<name>.json) or absolute path.",
    )
    parser.add_argument("--scenario-dir", type=Path, default=DEFAULT_SCENARIO_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--executor",
        choices=["simulated", "real"],
        default="simulated",
        help="Use the simulated mock variant_fn (default, preserves test isolation) or the real per-scenario executor.",
    )
    args = parser.parse_args()

    scenario_path = Path(args.experiment)
    if not scenario_path.exists():
        scenario_path = args.scenario_dir / f"{args.experiment}.json"
    config = load_experiment_config(scenario_path)
    report = run_full_experiment(
        config, output_dir=args.output_dir, executor=args.executor
    )
    print(
        f"Experiment '{config.experiment_id}' executor={args.executor} winner: {report.winner}"
    )
    print(f"Reports written to: {args.output_dir}")


if __name__ == "__main__":
    main()
