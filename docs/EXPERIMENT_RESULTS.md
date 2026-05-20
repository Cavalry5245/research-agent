# EXPERIMENT_RESULTS — Phase 2 A/B Experiment Summary

> Generated 2026-05-20 from `app/experiments/reports/*_report.json`.
> Results use the framework's default simulated executor; replace `variant_fn` to ground in live data.

## Headline Winners

| Experiment | Variant A | Variant B | Winner | Key Driver |
|---|---|---|---|---|
| prompt_comparison | full 13-section template | compact 8-section template | **B** | 35% faster generation, 35% fewer chars, coverage roughly unchanged |
| embedding_comparison | bge-small-zh-v1.5 | bge-large-zh-v1.5 | **B** | Hit@3 +0.09, MRR +0.06, at +66% retrieval latency |
| chunk_comparison | chunk_size=800, overlap=100 | chunk_size=500, overlap=50 | **A** | Lower indexing cost; small chunk only wins Hit@3 marginally |

## Detailed Deltas (B vs A)

### prompt_comparison

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| generation_time | 4.41 | 2.87 | -1.54 | -34.97% | 0.0000 | ✅ |
| content_length | 2994 | 1945 | -1049 | -35.04% | 0.0000 | ✅ |
| section_coverage | 0.851 | 0.892 | +0.041 | +4.81% | 0.6985 | ❌ |

Decision: **Adopt compact template by default**, escalate to full template when section_coverage
matters (e.g. literature reviews). Coverage delta is not statistically significant.

### embedding_comparison

| Metric | A | B | Δ | Relative | Notes |
|---|---|---|---|---|---|
| hit_at_3 | 0.78 | 0.87 | +0.09 | +11.5% | Major recall lift |
| mrr | 0.72 | 0.78 | +0.06 | +8.3% | First-result rank improves |
| retrieval_time | 0.18s | 0.30s | +0.12s | +66% | Higher dimension cost |

Decision: **Default to large embeddings for QA-critical paths**; keep small for indexing-heavy
batches where throughput dominates.

### chunk_comparison

| Metric | A (800/100) | B (500/50) | Δ | Notes |
|---|---|---|---|---|
| chunk_count | 18.75 | 30.00 | +60% | More chunks → more storage |
| hit_at_3 | 0.80 | 0.84 | +0.04 | Marginal |
| indexing_time | 3.87s | 5.00s | +29% | Higher cost |

Decision: **Keep 800/100 baseline**. Small chunks add cost without commensurate recall.

## Aggregate Recommendation

Configuration profile derived from cross-experiment winners:

```
LLM_NOTE_TEMPLATE=compact_8_section     # from prompt_comparison
EMBEDDING_MODEL=bge-large-zh-v1.5       # from embedding_comparison (QA path)
CHUNK_SIZE=800                          # from chunk_comparison
CHUNK_OVERLAP=100                       # from chunk_comparison
```

## Next Steps

1. Wire `ExperimentRunner` to the real services (replace `default_simulated_executor`).
2. Re-run all 3 experiments against the live LLM and reranker stack.
3. Capture per-paper variance by running each variant ≥ 5 times with different paper subsets,
   then re-evaluate p-values with real samples (current p-values use synthesized noise).
4. Feed winners into `app/config.py` defaults via a `phase2_winners.json` config layer.
