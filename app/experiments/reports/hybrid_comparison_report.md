# Experiment Report: hybrid_comparison

Compare vector-only (A) vs bm25-only (B) vs hybrid alpha=0.5 (C). Multiple-arm experiment uses A vs C primary comparison.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.7349 | 0.7842 |
| mrr | 0.6673 | 0.7461 |
| retrieval_time | 0.2338 | 0.2398 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.7349 | 0.7842 | +0.0494 | +6.72% | 0.5766 | ❌ |
| mrr | 0.6673 | 0.7461 | +0.0788 | +11.81% | 0.0205 | ✅ |
| retrieval_time | 0.2338 | 0.2398 | +0.0061 | +2.59% | 0.4931 | ❌ |

## Winner

**Selected variant**: B
