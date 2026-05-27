"""visualizer — Phase 2 matplotlib/seaborn plotting helpers.

Each plot function returns a matplotlib Figure (caller is responsible for save/show).
Designed so unit tests can verify return type and basic shape without rendering.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")  # headless-safe default
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

logger = logging.getLogger(__name__)

sns.set_theme(style="whitegrid", context="notebook")


def _save_or_return(fig: plt.Figure, output_path: str | Path | None) -> plt.Figure:
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=120, bbox_inches="tight")
        logger.info("Saved figure to %s", output)
    return fig


def plot_hit_at_k_curve(
    hit_at_k: dict[int, float],
    title: str = "Hit@K Retrieval Curve",
    output_path: str | Path | None = None,
) -> plt.Figure:
    ks = sorted(hit_at_k.keys())
    values = [hit_at_k[k] for k in ks]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ks, values, marker="o", linewidth=2)
    ax.set_xlabel("K")
    ax.set_ylabel("Hit@K")
    ax.set_ylim(0, 1.05)
    ax.set_title(title)
    for k, v in zip(ks, values):
        ax.annotate(
            f"{v:.2f}",
            (k, v),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=9,
        )
    return _save_or_return(fig, output_path)


def plot_response_time_distribution(
    timings: Iterable[float],
    title: str = "Response Time Distribution",
    output_path: str | Path | None = None,
) -> plt.Figure:
    arr = np.array(list(timings), dtype=float)
    fig, ax = plt.subplots(figsize=(6, 4))
    if arr.size == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
    else:
        sns.histplot(arr, kde=arr.size > 1, ax=ax, color="steelblue")
        ax.axvline(
            arr.mean(), color="red", linestyle="--", label=f"mean={arr.mean():.3f}s"
        )
        ax.legend()
    ax.set_xlabel("Seconds")
    ax.set_ylabel("Frequency")
    ax.set_title(title)
    return _save_or_return(fig, output_path)


def plot_failure_case_heatmap(
    failure_matrix: dict[str, dict[str, int]],
    title: str = "Failure Cases by Paper × Section",
    output_path: str | Path | None = None,
) -> plt.Figure:
    """failure_matrix: {paper_id: {section: count}}"""
    papers = sorted(failure_matrix.keys())
    all_sections = sorted(
        {s for sections in failure_matrix.values() for s in sections.keys()}
    ) or ["__no_data__"]
    data = np.zeros((len(papers), len(all_sections)), dtype=int)
    for i, paper in enumerate(papers):
        for j, section in enumerate(all_sections):
            data[i, j] = failure_matrix.get(paper, {}).get(section, 0)

    fig, ax = plt.subplots(
        figsize=(max(6, len(all_sections) * 0.8), max(3, len(papers) * 0.4))
    )
    if not papers:
        ax.text(
            0.5,
            0.5,
            "No failure data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
    else:
        sns.heatmap(
            data,
            annot=True,
            fmt="d",
            cmap="Reds",
            xticklabels=all_sections,
            yticklabels=papers,
            ax=ax,
            cbar_kws={"label": "failures"},
        )
    ax.set_xlabel("Section")
    ax.set_ylabel("Paper")
    ax.set_title(title)
    return _save_or_return(fig, output_path)


def plot_metric_comparison_bar(
    variants: dict[str, dict[str, float]],
    title: str = "A/B Variant Metric Comparison",
    output_path: str | Path | None = None,
) -> plt.Figure:
    """variants: {variant_name: {metric: value}}"""
    variant_names = list(variants.keys())
    metric_names = sorted({m for v in variants.values() for m in v.keys()}) or [
        "__no_metric__"
    ]
    n_metrics = len(metric_names)
    n_variants = len(variant_names)
    width = 0.8 / max(1, n_variants)

    fig, ax = plt.subplots(figsize=(max(6, n_metrics * 1.5), 4))
    x = np.arange(n_metrics)
    for i, variant in enumerate(variant_names):
        values = [variants[variant].get(metric, 0.0) for metric in metric_names]
        ax.bar(x + i * width, values, width=width, label=variant)
    ax.set_xticks(x + width * (n_variants - 1) / 2)
    ax.set_xticklabels(metric_names, rotation=20, ha="right")
    ax.set_ylabel("Score")
    ax.set_title(title)
    ax.legend()
    return _save_or_return(fig, output_path)


def plot_token_cost_trend(
    events: list[dict[str, Any]],
    title: str = "Cumulative Token/Time Cost Trend",
    output_path: str | Path | None = None,
) -> plt.Figure:
    """events: list of {timestamp, payload.total_time} dicts (JSONL-style)."""
    points: list[tuple[str, float]] = []
    for event in events:
        ts = event.get("timestamp") or ""
        t = (
            event.get("payload", {}).get("total_time")
            or event.get("payload", {}).get("llm_time")
            or 0.0
        )
        if ts:
            points.append((ts, float(t)))
    points.sort(key=lambda p: p[0])

    fig, ax = plt.subplots(figsize=(7, 4))
    if not points:
        ax.text(
            0.5, 0.5, "No event data", ha="center", va="center", transform=ax.transAxes
        )
    else:
        ys = np.cumsum([p[1] for p in points])
        ax.plot(range(len(points)), ys, marker=".", linewidth=1.5, color="darkorange")
        ax.set_xlabel("Event #")
        ax.set_ylabel("Cumulative seconds")
        ax.set_title(f"{title} (n={len(points)})")
    return _save_or_return(fig, output_path)


__all__ = [
    "plot_hit_at_k_curve",
    "plot_response_time_distribution",
    "plot_failure_case_heatmap",
    "plot_metric_comparison_bar",
    "plot_token_cost_trend",
]
