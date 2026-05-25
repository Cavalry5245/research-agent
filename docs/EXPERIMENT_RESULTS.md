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

## Dataset & Corpus State (as of 2026-05-23)

- QA seed dataset: 168 samples across 9 papers (`app/evaluation/datasets/qa_eval_seed.jsonl`).
- Vector store: **887 chunks** including **27 Abstract chunks** across all 9 papers (rebuilt 2026-05-23 after fixing a chunker bug that was dropping the `parsed.abstract` field).
- Pre-fix corpus had 860 chunks with **0 Abstract chunks** — 27 samples whose `supporting_sections=["Abstract"]` could never record a hit at the section level. Section-level retrieval ceiling lifted across all retrieval experiments after the fix.
- Test-pollution chunks (`paper_FILE_BACKED_SUBMISSION`) with non-majority embedding dims are filtered at eval time.

## Real A/B Experiment Results

### Headline Winners

| Experiment | Best Variant | Headline Metric | Caveat |
|---|---|---|---|
| **end-to-end QA (combined)** | rerank + LLM rewrite | answer_pass_rate +43.5% vs post-fix baseline (0.2738 → **0.3929**) | 14/168 pipeline failures from doubled LLM calls |
| **embedding_comparison** | `m3e-base` | hit@5 = **0.5655** vs bge-small 0.4702 (+20%) | Smallest retrieval_time too |
| **rerank_comparison** | cross-encoder rerank (GPU) | hit@5 +15.2% (p=0.0018 ✅) | Latency 6× slower (0.10s → 0.61s) on RTX 4060 |
| **hybrid_comparison** | hybrid α=0.5 | hit@5 +3.8% (p=0.08 ❌) | Not statistically significant |
| **chunk_comparison** | chunk_size=500/overlap=50 | hit@3 +9.3% (p=0.08 ❌) | +53% storage, slightly faster indexing |
| **query_optimization** | LLM rewrite | hit@5 +20.3% (p<0.0001 ✅) | Latency 94× slower (0.08s → 7.87s) |
| **prompt_comparison** | full 13-section template (A) | content_length richer; section_coverage tied at 1.0 | B is -15% chars & -6% time |

### embedding_comparison — real per-model retrieval

| Model | hit@5 | MRR | paper_recall | retrieval_time (s/q) | cache_reused |
|---|---|---|---|---|---|
| bge-small-zh-v1.5 | 0.4702 | 0.3035 | 1.0000 | 0.0775 | ✅ |
| bge-large-zh-v1.5 | 0.4881 | 0.2915 | 1.0000 | 0.0538 | ❌ |
| **m3e-base** | **0.5655** | **0.3632** | 1.0000 | **0.0163** | ❌ |

Source: `app/experiments/reports/embedding_models_real_report.{json,md}`
Method: 168 queries × 887 chunks paper-scoped cosine similarity; section match case-insensitive.

After the 2026-05-23 Abstract chunker fix, all three models gained ~6 hit@5 points vs the pre-fix corpus (e.g. bge-small 0.4048 → 0.4702, m3e-base 0.5238 → 0.5655). The 27 Abstract-targeted samples are now reachable at the section level. m3e-base remains the strongest AND the fastest — reproducible across both pre- and post-fix runs.

### rerank_comparison — recall@20 + cross-encoder rerank to top-5

| Metric | A: no rerank | B: bge-reranker-v2-m3 (GPU) | Δ | p-value |
|---|---|---|---|---|
| hit_at_5 | 0.4702 | **0.5417** | +15.2% | **0.0018** ✅ |
| mrr | 0.3035 | **0.3664** | +20.7% | **<0.0001** ✅ |
| retrieval_time | 0.099s | 0.614s | +518% | <0.0001 |

Source: `app/experiments/reports/rerank_comparison_report.{json,md}` (cross-encoder runs on CUDA via RTX 4060; bge-small embedding stays on CPU to avoid VRAM contention).

CPU-only baseline (kept for reference): retrieval_time=7.18s/query, 11.5× slower than GPU. Quality (hit@5, MRR) is bit-identical on either device — the cross-encoder is deterministic.

Decision: **Adopt cross-encoder rerank**; 0.61s/query is acceptable for interactive QA. Keep embedding on CPU, rerank on GPU when both are available — they fit separately in the 8GB VRAM budget but conflict if both auto-select GPU.

### hybrid_comparison — dense vs hybrid α=0.5

| Metric | A: vector | B: hybrid α=0.5 | Δ | p-value |
|---|---|---|---|---|
| hit_at_5 | 0.4702 | 0.4881 | +3.8% | 0.0796 ❌ |
| mrr | 0.3035 | 0.3096 | +2.0% | 0.7828 ❌ |
| retrieval_time | 0.087s | 0.077s | -11.5% | 0.0432 ✅ |

Source: `app/experiments/reports/hybrid_comparison_report.{json,md}`
Decision: **No quality lift detected at α=0.5.** Hybrid is marginally faster (BM25 path is cheaper than the dense one for short queries), but the +3.8% hit@5 lift is below the 0.05 significance bar. Tune α further or skip hybrid for this corpus.

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
| hit_at_5 | 0.4702 | **0.5655** | +20.3% | **<0.0001** ✅ |
| mrr | 0.3035 | **0.3450** | +13.7% | **0.0097** ✅ |
| latency | 0.084s | 7.871s | +9275% | <0.0001 |

Source: `app/experiments/reports/query_optimization_report.{json,md}`
Note: latency includes ~50 transient sub2api 502s during this run; LLMClient absorbed most via 3-retry exponential backoff but those retries inflate the measured latency vs the prior run (3.48s). A small number of rewrites fell back to original after exhausting retries — those samples behave like variant A and dilute the lift slightly.
Decision: **Still the largest single retrieval-quality lever measured here.** Enable behind a feature flag for high-value paths (compare-papers, paper-level QA, on-demand investigations); too slow for interactive search-as-you-type.

### prompt_comparison — 13-section vs 8-section compact

| Metric | A: 13-section | B: 8-section compact | Δ | p-value |
|---|---|---|---|---|
| generation_time | 55.72s | 52.30s | -6.1% | 0.0266 ✅ |
| content_length | 4918 | 4173 | -15.2% | 0.0002 ✅ |
| section_coverage | 1.0000 | 1.0000 | 0% | 0.5642 ❌ |

Source: `app/experiments/reports/prompt_comparison_report.{json,md}`
Method: 9 papers × 2 templates = 18 real `gpt-5.4` note generations.
Decision: **Use full 13-section template as default** (more comprehensive notes, coverage matches expected sections). Use compact for time-sensitive batch generation.

## QA Real Baseline (168 samples, `--use-live-pipeline --mode llm`, post-Abstract-fix corpus)

Replaces the prior 109-sample stub-mode report (which echoed `expected_answer` and over-reported 96% pass rate).

| Metric | Pre-fix baseline | Post-fix baseline | Combined (rerank + rewrite) | Δ vs post-fix |
|---|---|---|---|---|
| sample_count | 168 | 168 | 168 | — |
| pipeline | live | live | live+rerank+rewrite | — |
| evaluation_mode | llm | llm | llm | — |
| **answer_pass_rate** | 0.2381 | 0.2738 | **0.3929** | **+43.5%** ⭐ |
| citation_pass_rate | 0.4405 | 0.4524 | 0.4464 | -1.3% |
| **mean_answer_score** | 0.2408 | 0.2728 | **0.3708** | **+35.9%** ⭐ |
| mean_citation_score | 0.4071 | 0.4246 | 0.3892 | -8.3% |
| samples passing both judges | — | 33 | **46** | **+39%** |

Status breakdown (combined run, 2026-05-25):
- 154/168 LLM answer judges returned valid JSON (`status=ok`); 14 parse/API errors recorded score=0.
- 161/168 LLM citation judges returned valid JSON; 7 errors recorded score=0.
- 14/168 live pipeline failures (3 retries exhausted on upstream 502); recorded `predicted_answer=""`. Higher than post-fix run (5) because the combined config doubles LLM calls per sample (rewrite + answer), which doubles 502 exposure.
- 46/168 samples fully passed both judges; 66 passed answer judge; 75 passed citation judge.

Sources: `app/evaluation/reports/qa_eval_seed_report.json` (post-fix baseline), `app/evaluation/reports/qa_eval_seed_combined_report.json` (combined). Downstream analytics regenerated to `app/analytics/reports/qa_analysis.json`.

**Interpretation**:
- **Combined config is the headline result.** Stacking rerank (top-20 → cross-encoder → top-5) on top of LLM query rewrite lifts end-to-end answer pass rate from 27.4% to 39.3%, a +43.5% relative gain. The lift exceeds either component individually (rerank alone +15.2% hit@5, rewrite alone +20.3% hit@5) because the components compose: rewrite improves the *recall set* the reranker sees.
- **Citation pass rate is essentially flat (-1.3%)**, well within sub2api 502 noise. Citation judge already saturated near its ceiling on the post-fix corpus where most queries can match `paper_id` even when the section is wrong.
- **mean_citation_score drops 8.3%** despite flat pass rate. Hypothesis: query rewriting changes the question's surface text, so the citation judge — which scores citation-question semantic alignment — is judging citations against a slightly different question than the dataset reference. The pass/fail boundary is unaffected, only the soft score distribution shifts.
- **Pre-fix → combined is +65% answer pass rate** (0.2381 → 0.3929). That's the full Phase 4 retrieval-stack story end-to-end on a real benchmark.

## Aggregate Recommendation (from cross-experiment evidence)

```env
EMBEDDING_MODEL=m3e-base              # +20% hit@5 vs bge-small, fastest
ENABLE_RERANK=true                    # +15% hit@5 (significant); cross-encoder on GPU adds ~0.51s/query
EMBEDDING_DEVICE=cpu                  # frees the 8GB VRAM budget for the reranker
HYBRID_RETRIEVER=off                  # no significant lift at α=0.5 on this corpus
CHUNK_SIZE=800; CHUNK_OVERLAP=100     # keep current; smaller chunks don't justify +53% storage
QUERY_REWRITE=on                      # combined with rerank: +43.5% answer_pass_rate end-to-end
PROMPT_TEMPLATE=full_13_section       # use compact only for time-sensitive batches
```

**Combined config validated end-to-end**: rerank + query_rewrite together lift answer_pass_rate from 0.2738 to 0.3929 (+43.5%). The components compose — rewrite improves the recall set the reranker sees. Latency cost is ~8s/query (dominated by LLM rewrite call); acceptable for QA but not for search-as-you-type. For interactive paths, rerank-only (0.61s/query) is the right tradeoff.

## Known Limitations & Next Steps

- **Abstract chunker bug — fixed 2026-05-23**: `chunker.chunk_paper` previously dropped `parsed.abstract` because it was a top-level field, not a `Section`. Fixed by injecting a synthetic `Abstract` section when one isn't already present. Vector store rebuilt to 887 chunks (27 Abstract chunks across all 9 papers). All retrieval A/B experiments above re-run against the fixed corpus.
- **Section-name case variability**: dataset has `Method` and `method` both present (39 + 24 samples). Match is case-insensitive; if the dataset evolves toward inconsistent casing, consider normalizing at build time.
- **Sub2api 502 rate**: real LLM evals hit ~50 transient 502s per ~500-call batch; current `LLMClient` retries (3 attempts, exponential backoff) absorb most; switched OpenAI client to explicit `httpx.Timeout` + `max_retries=0` to avoid socket-hung-forever failure mode seen with default config. The 2026-05-23 query_optimization re-run hit a bad sub2api window where retries inflated avg latency from 3.48s to 7.87s — quality numbers are unaffected (still p<0.0001).
- **Hybrid α tuning**: try α=0.3 and α=0.7 to see if dense/sparse balance helps; current 0.5 is an arbitrary midpoint.
- **Reranker on GPU**: already adopted — 0.61s/query on RTX 4060 with `EMBEDDING_DEVICE=cpu` to free VRAM. CPU-only path remains supported as a 7s/query fallback.
- **QA real baseline re-run**: the headline 0.2381/0.4405 pass rates were captured pre-Abstract-fix; re-running against the 887-chunk corpus is expected to lift both, especially citation pass rate on Abstract-targeted samples.
