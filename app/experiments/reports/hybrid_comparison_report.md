# Experiment Report: hybrid_comparison

Compare vector-only (A) vs bm25-only (B) vs hybrid alpha=0.5 (C). Multiple-arm experiment uses A vs C primary comparison.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.4702 | 0.4881 |
| mrr | 0.3035 | 0.3096 |
| retrieval_time | 0.0872 | 0.0772 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.4702 | 0.4881 | +0.0179 | +3.80% | 0.0796 | ❌ |
| mrr | 0.3035 | 0.3096 | +0.0062 | +2.03% | 0.7828 | ❌ |
| retrieval_time | 0.0872 | 0.0772 | -0.0100 | -11.45% | 0.0432 | ✅ |

## Winner

**Selected variant**: B
