# EXPERIMENT_GUIDE — A/B Testing Framework

ResearchAgent Phase 2 ships a configuration-driven A/B testing harness. This guide explains how
to define, run, and interpret experiments.

## Architecture

```
app/experiments/
├── config.py                 # ExperimentConfig + VariantConfig (Pydantic)
├── runner.py                 # ExperimentRunner + compare_variants + generate_report
├── scenarios/                # JSON experiment definitions
│   ├── prompt_comparison.json
│   ├── embedding_comparison.json
│   └── chunk_comparison.json
└── reports/                  # Generated MD + JSON reports
```

## Defining an Experiment

Create a JSON file under `app/experiments/scenarios/<name>.json`:

```json
{
  "experiment_id": "my_experiment",
  "description": "What is being tested",
  "metric_keys": ["accuracy", "latency"],
  "higher_is_better": ["accuracy"],
  "dataset": "path/to/dataset.jsonl",
  "variants": [
    {"variant": "A", "description": "Baseline", "parameters": {"flag": false}},
    {"variant": "B", "description": "Treatment", "parameters": {"flag": true}}
  ]
}
```

Required fields:
- `experiment_id`: unique slug
- `metric_keys`: which numeric outputs to compare
- `higher_is_better`: subset of metric_keys whose values should grow (others minimized)
- `variants`: exactly two for now (A vs B)

## Running an Experiment

```bash
python -m app.experiments.runner --experiment my_experiment
```

This writes both `app/experiments/reports/my_experiment_report.md` (human-readable summary) and
`my_experiment_report.json` (machine-readable).

## Interpreting the Report

The Markdown report includes:
1. **Variant Metrics** — raw metric values per variant.
2. **Deltas & Significance** — Δ, relative change, Welch t-test p-value per metric.
3. **Winner** — derived from the variant that wins more metrics (weighted equally; ties marked).

Significance is computed via `scipy.stats.ttest_ind` over 10 synthesized samples per metric
(each is a Gaussian-noised perturbation of the headline value, seeded deterministically).

## Plugging in a Real Executor

By default the runner uses `default_simulated_executor` which returns mocked metric values keyed
off the variant parameters — useful for framework smoke tests. For a real experiment, pass your
own `variant_fn` to `ExperimentRunner`:

```python
from app.experiments import ExperimentRunner, load_experiment_config

def my_variant_fn(variant_cfg):
    # actually run the QA pipeline / index / etc. with variant_cfg.parameters
    return {"accuracy": 0.86, "latency": 0.21}

config = load_experiment_config("app/experiments/scenarios/my_experiment.json")
runner = ExperimentRunner(config, variant_fn=my_variant_fn)
results = runner.run_experiment()
```

## Built-in Scenarios

| Scenario | What it Tests | Default Winner |
|---|---|---|
| `prompt_comparison` | full 13-section template vs compact 8-section | (see report) |
| `embedding_comparison` | bge-small-zh vs bge-large-zh | (see report) |
| `chunk_comparison` | chunk_size=800/overlap=100 vs 500/50 | (see report) |

## Adding Statistical Rigor

When using a real executor, generate >= 5 independent samples per metric (e.g. across paper IDs
or random seeds) and stash them in `VariantResult.samples`. The Welch t-test will then use real
data instead of synthesized noise.
