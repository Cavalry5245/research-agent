# Experiment Report: rerank_comparison

Compare no-rerank (A) vs cross-encoder rerank with BAAI/bge-reranker-v2-m3 (B). Recall top_k=20, final top_k=5.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.7349 | 0.8442 |
| mrr | 0.6673 | 0.7861 |
| retrieval_time | 0.2338 | 0.3898 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.7349 | 0.8442 | +0.1094 | +14.88% | 0.0000 | ✅ |
| mrr | 0.6673 | 0.7861 | +0.1188 | +17.81% | 0.0006 | ✅ |
| retrieval_time | 0.2338 | 0.3898 | +0.1561 | +66.75% | 0.0000 | ✅ |

## Winner

**Selected variant**: B
