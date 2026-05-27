"""Unit tests for app/experiments/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.experiments.config import (
    ExperimentConfig,
    VariantConfig,
    load_experiment_config,
)
from app.experiments.runner import (
    ComparisonReport,
    ExperimentRunner,
    VariantResult,
    compare_variants,
    default_simulated_executor,
    generate_report,
    run_full_experiment,
)


def _make_config(experiment_id: str = "demo") -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id=experiment_id,
        description="demo",
        metric_keys=["score", "latency"],
        higher_is_better=["score"],
        variants=[
            VariantConfig(
                variant="A", parameters={"flag": False}, description="baseline"
            ),
            VariantConfig(
                variant="B", parameters={"flag": True}, description="treatment"
            ),
        ],
    )


def test_experiment_config_validation():
    cfg = _make_config()
    assert cfg.variant_names() == ["A", "B"]
    assert cfg.variant("A").parameters == {"flag": False}
    with pytest.raises(KeyError):
        cfg.variant("Z")


def test_load_experiment_config_from_json(tmp_path: Path):
    path = tmp_path / "exp.json"
    path.write_text(
        json.dumps(
            {
                "experiment_id": "exp_x",
                "description": "x",
                "metric_keys": ["m"],
                "higher_is_better": ["m"],
                "variants": [
                    {"variant": "A", "parameters": {}},
                    {"variant": "B", "parameters": {}},
                ],
            }
        ),
        encoding="utf-8",
    )
    cfg = load_experiment_config(path)
    assert cfg.experiment_id == "exp_x"


def test_default_simulated_executor_returns_metrics():
    metrics = default_simulated_executor(
        VariantConfig(variant="A", parameters={"prompt_module": "x"})
    )
    assert "generation_time" in metrics
    assert "content_length" in metrics


def test_experiment_runner_executes_all_variants():
    cfg = _make_config()
    runner = ExperimentRunner(
        cfg,
        variant_fn=lambda v: {
            "score": 0.8 if v.variant == "A" else 0.9,
            "latency": 1.0,
        },
    )
    results = runner.run_experiment()
    assert len(results) == 2
    assert all(r.samples["score"] for r in results)


def test_compare_variants_selects_winner_on_higher_is_better():
    a = VariantResult(
        variant="A",
        metrics={"score": 0.8, "latency": 1.0},
        samples={"score": [0.8] * 10, "latency": [1.0] * 10},
    )
    b = VariantResult(
        variant="B",
        metrics={"score": 0.9, "latency": 0.9},
        samples={"score": [0.9] * 10, "latency": [0.9] * 10},
    )
    deltas, sig, winner = compare_variants(
        [a, b], metric_keys=["score", "latency"], higher_is_better=["score"]
    )
    assert winner == "B"
    assert deltas["score"]["delta"] == pytest.approx(0.1)
    assert "p_value" in sig["score"]


def test_compare_variants_returns_none_with_single_variant():
    a = VariantResult(variant="A", metrics={"score": 0.8})
    deltas, sig, winner = compare_variants(
        [a], metric_keys=["score"], higher_is_better=["score"]
    )
    assert deltas == {}
    assert winner is None


def test_generate_report_writes_markdown(tmp_path: Path):
    comparison = ComparisonReport(
        experiment_id="r",
        description="d",
        variant_results=[
            VariantResult(variant="A", metrics={"score": 0.7}),
            VariantResult(variant="B", metrics={"score": 0.9}),
        ],
        deltas={
            "score": {
                "variant_a": 0.7,
                "variant_b": 0.9,
                "delta": 0.2,
                "relative_change": 0.286,
            }
        },
        significance={
            "score": {"test": "welch_t", "p_value": 0.001, "significant_at_0.05": True}
        },
        winner="B",
    )
    path = tmp_path / "out.md"
    body = generate_report(comparison, output_path=path)
    assert path.exists()
    assert "Winner" in body
    assert "**Selected variant**: B" in body
    assert "score" in body


def test_run_full_experiment_creates_md_and_json(tmp_path: Path):
    cfg = _make_config("integration_demo")
    report = run_full_experiment(cfg, output_dir=tmp_path)
    md = tmp_path / "integration_demo_report.md"
    js = tmp_path / "integration_demo_report.json"
    assert md.exists()
    assert js.exists()
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["experiment_id"] == "integration_demo"
    assert len(payload["variants"]) == 2


def test_scenario_files_load_and_run(tmp_path: Path):
    """Smoke test that ships-shipping scenario files parse and execute."""
    scenarios_dir = Path("app/experiments/scenarios")
    for scenario_file in scenarios_dir.glob("*.json"):
        cfg = load_experiment_config(scenario_file)
        assert cfg.experiment_id
        report = run_full_experiment(cfg, output_dir=tmp_path)
        assert report.winner in {"A", "B", None}
