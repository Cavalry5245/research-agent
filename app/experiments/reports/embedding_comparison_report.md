# Experiment Report: embedding_comparison

Compare bge-small-zh-v1.5 (A) vs bge-large-zh-v1.5 (B) on retrieval quality.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_3 | 0.7715 | 0.8071 |
| mrr | 0.6988 | 0.7735 |
| retrieval_time | 0.2191 | 0.2972 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_3 | 0.7715 | 0.8071 | +0.0356 | +4.62% | 0.3585 | ❌ |
| mrr | 0.6988 | 0.7735 | +0.0747 | +10.69% | 0.0000 | ✅ |
| retrieval_time | 0.2191 | 0.2972 | +0.0781 | +35.64% | 0.0000 | ✅ |

## Winner

**Selected variant**: B
