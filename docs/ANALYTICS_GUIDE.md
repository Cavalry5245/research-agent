# ANALYTICS_GUIDE — Phase 2 Analytics Architecture

Phase 2 adds an analytics layer that observes the service pipeline (QA / comparison / note /
indexing), persists events to JSONL, and provides analysis + visualization helpers.

## Module Layout

```
app/analytics/
├── __init__.py              # re-exports AnalyticsCollector, AnalyticsEvent, get_collector
├── data_collector.py        # AnalyticsCollector — append-only JSONL event sink
├── analyze_retrieval.py     # Hit@K curve, failure clusters from retrieval reports
├── analyze_qa.py            # Answer length, citation accuracy, time breakdowns
├── analyze_comparison.py    # Aspect coverage, quality score distribution
├── failure_detector.py      # FailureDetector — threshold-based fault classification
├── failure_analyzer.py      # FailureAnalyzer — clustering + Markdown report
├── visualizer.py            # 5 plotting helpers (matplotlib + seaborn)
└── reports/                 # Generated JSON/Markdown summaries
```

## Data Flow

```
Service path                                Analytics path
─────────────                                 ───────────────
paper_qa.answer_question  ──────────────►  _emit_qa_event → collector.log_qa_request
paper_compare.compare_papers ───────────►  _emit_comparison_event
note_generator.generate_note ───────────►  _emit_note_event
                                            │
                                            ▼
                                  app/storage/analytics/events.jsonl

failure_detector.detect_*  ─────────────►  collector.log_failure
                                            │
                                            ▼
                                  app/storage/analytics/failures.jsonl
```

All emit calls are best-effort: failures in the analytics path never break the main service flow.

## AnalyticsCollector

Singleton accessor: `app.analytics.get_collector()`. Honors:
- `ANALYTICS_EVENTS_PATH` env var (default `app/storage/analytics/events.jsonl`)
- `ANALYTICS_FAILURES_PATH` env var (default `app/storage/analytics/failures.jsonl`)

API:
- `log_qa_request(paper_id, question, answer, retrieval_time, llm_time, sources_count, top_k, extra=None)`
- `log_comparison(paper_ids, generation_time, result_length, aspects_count, extra=None)`
- `log_indexing(paper_id, chunk_count, embedding_time, parse_time, persist_time, extra=None)`
- `log_note(paper_id, llm_time, content_length, extra=None)`
- `log_failure(failure_type, context, reason=None)`
- `read_events(event_type=None) -> list[AnalyticsEvent]`
- `read_failures(failure_type=None) -> list[AnalyticsEvent]`

## Analysis Entry Points

```bash
# Retrieval
python -m app.analytics.analyze_retrieval \
    --input app/evaluation/reports/retrieval_eval_seed_report.json

# QA
python -m app.analytics.analyze_qa \
    --input app/evaluation/reports/qa_eval_seed_report.json

# Comparison
python -m app.analytics.analyze_comparison \
    --input app/evaluation/reports/comparison_eval_seed_report.json

# Failures
python -m app.analytics.failure_analyzer
```

Each writes a JSON report under `app/analytics/reports/` and prints a summary to stdout.

## Visualizers

Each plot function returns a `matplotlib.figure.Figure` (set `Agg` backend by default) so the
caller can either show interactively (`fig.show()`) or save (`output_path=...`).

| Function | Use Case |
|---|---|
| `plot_hit_at_k_curve` | Retrieval Hit@K vs K |
| `plot_response_time_distribution` | Latency histogram + KDE |
| `plot_failure_case_heatmap` | Failures by paper × section |
| `plot_metric_comparison_bar` | A/B variant metric bars |
| `plot_token_cost_trend` | Cumulative cost over events |

## Extension Points

- New event types — add to `EVENT_TYPES` set in `data_collector.py` and write a `log_xxx` helper.
- New analyzer — drop a new `analyze_<topic>.py` and reuse the `time_distribution` / cluster helpers.
- New plotter — add to `visualizer.py`, follow the `_save_or_return(fig, output_path)` pattern.
- LLM judges — `app/evaluation/judges.py` ships `LLMAnswerJudge` + `LLMCitationJudge` (build via
  `build_judges("llm")`). Both accept a `llm_call` callable for test injection; default to the
  configured `LLMClient`. Prompts live in `app/evaluation/prompts/judge_prompts.py`.

## Performance

Single emit call < 1ms (file append + JSON serialize). Service-layer instrumentation adds
`time.perf_counter()` measurements and a single best-effort write; benchmark in
`tests/test_paper_qa.py` confirms the QA happy path stays under historical timings.

## Testing

- `tests/test_analytics.py` — 21 tests (collector, analyzers, plotters)
- `tests/test_failure_analyzer.py` — 20 tests (detector + analyzer)
- `tests/test_experiments.py` — 9 tests (config, runner, comparison report)
- `tests/test_qa_evaluator.py` — 8 tests including live pipeline path
- `tests/test_evaluation_judges.py` — 18 tests (rule-based + placeholder + 11 LLM judge tests)
