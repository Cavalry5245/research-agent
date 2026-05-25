# Notebooks — Phase 2 Analytics

Four Jupyter notebooks that exercise the Phase 2 analytics and experiments modules end-to-end.

| Notebook | Focus | Required artifacts |
|---|---|---|
| `01_retrieval_analysis.ipynb` | Hit@K, MRR, retrieval failure clusters | `app/evaluation/reports/retrieval_eval_seed_report.json` |
| `02_qa_quality_analysis.ipynb` | Answer length, citation accuracy, statistical tests | `app/evaluation/reports/qa_eval_seed_report.json` |
| `03_experiment_comparison.ipynb` | Visualize A/B prompt / embedding / chunk experiments | `app/experiments/reports/*_report.json` |
| `04_failure_case_study.ipynb` | Failure mode pie chart, case inspection, fix suggestions | `app/storage/analytics/failures.jsonl` |

## How to run

```bash
# 1) From the repo root, ensure all upstream reports are fresh
python -m app.evaluation.scripts.evaluate_retrieval
python -m app.evaluation.scripts.evaluate_qa
python -m app.evaluation.scripts.evaluate_comparison
python -m app.experiments.runner --experiment prompt_comparison
python -m app.experiments.runner --experiment embedding_comparison
python -m app.experiments.runner --experiment chunk_comparison

# 2) Launch jupyter (or execute headlessly)
jupyter notebook notebooks/

# 3) Headless re-execution for CI / smoke tests
jupyter nbconvert --to notebook --execute notebooks/01_retrieval_analysis.ipynb \
    --output 01_retrieval_analysis.executed.ipynb
```

## Dependencies

Installed via `requirements.txt`:
- pandas >= 2.0
- numpy >= 1.24
- matplotlib >= 3.7
- seaborn >= 0.12
- scipy >= 1.11
- jupyter >= 1.0

## Conventions

- Each notebook adds the repo root to `sys.path` so it can be launched from `notebooks/` or the repo root.
- Plots default to seaborn `whitegrid` style (set in `app/analytics/visualizer.py`).
- Notebooks are intentionally short — heavy logic lives in `app/analytics/` so it can be unit-tested.

## Live data caveat

All seed reports currently come from deterministic stubs. To get realistic distributions:

```bash
python -m app.evaluation.scripts.evaluate_qa --use-live-pipeline
```

This calls `paper_qa.answer_question` against `VectorStore + EmbeddingClient + LLMClient`, which
in turn triggers the analytics collector to populate `app/storage/analytics/events.jsonl` with
real retrieval / LLM latencies.
