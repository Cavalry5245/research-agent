# Experiment Report: hybrid_comparison

Compare vector-only (A) vs bm25-only (B) vs hybrid alpha=0.5 (C). Multiple-arm experiment uses A vs C primary comparison.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.4048 | 0.4107 |
| mrr | 0.2780 | 0.2700 |
| retrieval_time | 0.2519 | 0.2417 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.4048 | 0.4107 | +0.0060 | +1.47% | 0.7876 | ❌ |
| mrr | 0.2780 | 0.2700 | -0.0079 | -2.86% | 0.2207 | ❌ |
| retrieval_time | 0.2519 | 0.2417 | -0.0102 | -4.07% | 0.0386 | ✅ |

## Winner

**Selected variant**: B
