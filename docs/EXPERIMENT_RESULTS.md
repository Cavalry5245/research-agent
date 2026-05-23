# EXPERIMENT_RESULTS — Real A/B Evaluation Summary

> Generated 2026-05-22 from `app/experiments/reports/*_report.json` and `app/evaluation/reports/qa_eval_seed_report.json`.
> **All numbers below are produced by real executors against the 168-sample QA seed dataset (or per-paper metadata where noted).** Replaces the prior Phase 2 simulated baseline.

## ⭐ Judge Choice Still Dominates Quality Reading

Live 10-sample evaluation (real `gpt-5.4` via sub2api) scored twice — rule-based token-overlap vs LLM-as-judge:

| Metric | Rule-based judge | LLM judge | Δ |
|---|---|---|---|
| answer_pass_rate | 0.10 | **0.40** | +300% |
| citation_pass_rate | 0.20 | 0.30 | +50% |
| mean_answer_score | 0.11 | **0.40** | +264% |
| mean_citation_score | 0.20 | 0.33 | +66% |

Source: `app/evaluation/reports/qa_eval_live_10sample_llmjudge_report.json`

**Why the rule judge under-reports**:
1. **Chinese long-form answers** — model writes 1000-2700 char detailed Chinese, reference is a 320-char abstract excerpt; token overlap is naturally low even when the answer is semantically correct.
2. **Abstention handling** — for out-of-scope probes where the expected answer is "原文未明确说明", the model abstains correctly but the rule judge scores 0.00 because strings don't overlap. LLM judge scores those 1.00.
3. **False positives caught** — LLM judge also caught two cases where rule gave partial credit (0.09-0.12) for accidental token overlap on actually-wrong answers, scoring them 0.00.

**Decision**: Use `--mode llm` for any meaningful answer-quality measurement. Rule-based stays useful as a free smoke check.

## Dataset & Corpus State (as of 2026-05-22)

- QA seed dataset: 168 samples across 9 papers (`app/evaluation/datasets/qa_eval_seed.jsonl`).
- Vector store: 860 chunks (4 test-pollution chunks `paper_FILE_BACKED_SUBMISSION` are filtered at eval time).
- Known coverage gap: **no `Abstract` section chunks indexed**; 27 samples whose `supporting_sections=["Abstract"]` will record 0 hit@k under strict section matching for every model — see `paper_recall=1.0` in the embedding eval. This gap is the primary reason absolute hit@5 numbers look low; it is corpus-side, not model-side.

## Real A/B Experiment Results

### Headline Winners

| Experiment | Best Variant | Headline Metric | Caveat |
|---|---|---|---|
| **embedding_comparison** | `m3e-base` | hit@5 = **0.5238** vs bge-small 0.4048 (+29%) | Smallest retrieval_time too |
| **rerank_comparison** | cross-encoder rerank (GPU) | hit@5 +19.1% (p<0.0001 ✅) | Latency 6× slower (0.10s → 0.65s) on RTX 4060 |
| **hybrid_comparison** | hybrid α=0.5 | hit@5 +1.5% (p=0.79 ❌) | Not statistically significant |
| **chunk_comparison** | chunk_size=500/overlap=50 | hit@3 +9.3% (p=0.08 ❌) | +53% storage, slightly faster indexing |
| **query_optimization** | LLM rewrite | hit@5 +33.8% (p<0.0001 ✅) | Latency 39× slower (0.09s → 3.48s) |
| **prompt_comparison** | full 13-section template (A) | content_length richer; section_coverage tied at 1.0 | B is -15% chars & -6% time |

### embedding_comparison — real per-model retrieval

| Model | hit@5 | MRR | paper_recall | retrieval_time (s/q) | cache_reused |
|---|---|---|---|---|---|
| bge-small-zh-v1.5 | 0.4048 | 0.2780 | 1.0000 | 0.1145 | ✅ |
| bge-large-zh-v1.5 | 0.4583 | 0.3008 | 1.0000 | 0.0580 | ❌ |
| **m3e-base** | **0.5238** | **0.3460** | 1.0000 | **0.0166** | ❌ |

Source: `app/experiments/reports/embedding_models_real_report.{json,md}`
Method: 168 queries × 860 chunks paper-scoped cosine similarity; section match case-insensitive.

Real numbers are well below the previous simulated baseline (bge-small 0.76 → real 0.40), because (a) 27 Abstract-targeted samples hit the corpus gap, (b) section-level matching is strict. m3e-base materially outperforms both BGE variants AND is the fastest — surprising but reproducible.

### rerank_comparison — recall@20 + cross-encoder rerank to top-5

| Metric | A: no rerank | B: bge-reranker-v2-m3 (GPU) | Δ | p-value |
|---|---|---|---|---|
| hit_at_5 | 0.4048 | **0.4821** | +19.1% | **<0.0001** ✅ |
| mrr | 0.2780 | **0.3162** | +13.7% | **0.0240** ✅ |
| retrieval_time | 0.105s | 0.654s | +524% | <0.0001 |

Source: `app/experiments/reports/rerank_comparison_report.{json,md}` (cross-encoder runs on CUDA via RTX 4060; bge-small embedding stays on CPU to avoid VRAM contention).

CPU-only baseline (kept for reference): retrieval_time=7.18s/query, 11.5× slower than GPU. Quality (hit@5, MRR) is bit-identical on either device — the cross-encoder is deterministic.

Decision: **Adopt cross-encoder rerank**; 0.65s/query (p95 ≈ 0.85s) is acceptable for interactive QA. Keep embedding on CPU, rerank on GPU when both are available — they fit fine separately in the 8GB VRAM budget but conflict if both auto-select GPU.

### hybrid_comparison — dense vs hybrid α=0.5

| Metric | A: vector | B: hybrid α=0.5 | Δ | p-value |
|---|---|---|---|---|
| hit_at_5 | 0.4048 | 0.4107 | +1.5% | 0.7876 ❌ |
| mrr | 0.2780 | 0.2700 | -2.9% | 0.2207 ❌ |
| retrieval_time | 0.252s | 0.242s | -4.1% | 0.0386 ✅ |

Source: `app/experiments/reports/hybrid_comparison_report.{json,md}`
Decision: **No quality lift detected at α=0.5.** Either tune α further (the current corpus may favor dense), expand to BM25-only variant C, or skip hybrid for this corpus.

### chunk_comparison — 800/100 vs 500/50

| Metric | A: 800/100 | B: 500/50 | Δ | p-value |
|---|---|---|---|---|
| chunk_count | 860 | 1318 | +53% | <0.0001 ✅ |
| hit_at_3 | 0.3214 | 0.3512 | +9.3% | 0.0798 ❌ |
| indexing_time | 77.09s | 68.31s | -11.4% | 0.0001 ✅ |

Source: `app/experiments/reports/chunk_comparison_report.{json,md}`
Decision: **Keep 800/100 default**. hit@3 lift is not significant and storage grows 53%. Smaller chunks indexed slightly faster mainly because individual encode batches are shorter.

### query_optimization — original vs LLM rewrite

| Metric | A: original | B: LLM rewrite | Δ | p-value |
|---|---|---|---|---|
| hit_at_5 | 0.4048 | **0.5417** | +33.8% | **<0.0001** ✅ |
| mrr | 0.2780 | **0.3255** | +17.1% | **0.0056** ✅ |
| latency | 0.089s | 3.481s | +3802% | <0.0001 |

Source: `app/experiments/reports/query_optimization_report.{json,md}`
Note: 166/168 rewrites succeeded; 2 fell back to original after 3 retries.
Decision: **Largest single retrieval-quality lever measured here.** Enable behind a feature flag for high-value paths (compare-papers, paper-level QA, on-demand investigations); too slow for interactive search-as-you-type.

### prompt_comparison — 13-section vs 8-section compact

| Metric | A: 13-section | B: 8-section compact | Δ | p-value |
|---|---|---|---|---|
| generation_time | 55.72s | 52.30s | -6.1% | 0.0266 ✅ |
| content_length | 4918 | 4173 | -15.2% | 0.0002 ✅ |
| section_coverage | 1.0000 | 1.0000 | 0% | 0.5642 ❌ |

Source: `app/experiments/reports/prompt_comparison_report.{json,md}`
Method: 9 papers × 2 templates = 18 real `gpt-5.4` note generations.
Decision: **Use full 13-section template as default** (more comprehensive notes, coverage matches expected sections). Use compact for time-sensitive batch generation.

## QA Real Baseline (168 samples, `--use-live-pipeline --mode llm`)

Replaces the prior 109-sample stub-mode report (which echoed `expected_answer` and over-reported 96% pass rate).

| Metric | Value |
|---|---|
| sample_count | 168 |
| pipeline | live |
| evaluation_mode | llm |
| **answer_pass_rate** | **0.2381** |
| **citation_pass_rate** | **0.4405** |
| mean_answer_score | 0.2408 |
| mean_citation_score | 0.4071 |

Status breakdown:
- 163/168 LLM answer judges returned valid JSON (`status=ok`); 5 parse errors recorded score=0.
- 164/168 LLM citation judges returned valid JSON; 4 parse errors recorded score=0.
- 4/168 live pipeline failures (3 retries exhausted on upstream 502); recorded `predicted_answer=""`.
- 32/168 samples fully passed both judges; 40 passed answer judge; 74 passed citation judge.

Source: `app/evaluation/reports/qa_eval_seed_report.json`. Downstream analytics regenerated to `app/analytics/reports/qa_analysis.json`.

**Interpretation**: The drop from the stub-mode 96.3% pass rate is the entire signal — stub mode echoed the reference answer so judges trivially passed. The real LLM-generated answer is judged against the same reference and pass rate honestly reflects answer-quality gap. Citation pass rate (44%) is higher because cited paper_id usually matches even when the cited section disagrees with `supporting_sections` (e.g. the answer cites `method` chunks for an `Abstract`-targeted question — the corpus has no Abstract chunks at all, so any non-empty citation is partial).

## Aggregate Recommendation (from cross-experiment evidence)

```env
EMBEDDING_MODEL=m3e-base              # +29% hit@5 vs bge-small, fastest
ENABLE_RERANK=true                    # +19% hit@5 (significant); cross-encoder on GPU adds only ~0.55s/query
EMBEDDING_DEVICE=cpu                  # frees the 8GB VRAM budget for the reranker
HYBRID_RETRIEVER=off                  # no significant lift at α=0.5 on this corpus
CHUNK_SIZE=800; CHUNK_OVERLAP=100     # keep current; smaller chunks don't justify +53% storage
QUERY_REWRITE=on-for-async-paths      # +34% hit@5 but 39× slower; gate behind feature flag
PROMPT_TEMPLATE=full_13_section       # use compact only for time-sensitive batches
```

## Known Limitations & Next Steps

- **Abstract section gap**: chunker did not emit `Abstract` chunks for any of the 9 indexed papers; 27 samples whose `supporting_sections` is exactly `["Abstract"]` cannot be solved at the section level today. Add an Abstract-emitting chunking pass to lift the absolute hit@5 ceiling.
- **Section-name case variability**: dataset has `Method` and `method` both present (39 + 24 samples). Match is case-insensitive; if the dataset evolves toward inconsistent casing, consider normalizing at build time.
- **Sub2api 502 rate**: real LLM evals hit ~50 transient 502s per ~500-call batch; current `LLMClient` retries (3 attempts, exponential backoff) absorb most; switched OpenAI client to explicit `httpx.Timeout` + `max_retries=0` to avoid socket-hung-forever failure mode seen with default config.
- **Hybrid α tuning**: try α=0.3 and α=0.7 to see if dense/sparse balance helps; current 0.5 is an arbitrary midpoint.
- **Reranker on GPU**: already adopted — 0.65s/query on RTX 4060 with `EMBEDDING_DEVICE=cpu` to free VRAM. CPU-only path remains supported as a 7s/query fallback.
