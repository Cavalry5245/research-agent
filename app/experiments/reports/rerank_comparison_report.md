# Experiment Report: rerank_comparison

Compare no-rerank (A) vs cross-encoder rerank with BAAI/bge-reranker-v2-m3 (B). Recall top_k=20, final top_k=5.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.4702 | 0.5417 |
| mrr | 0.3035 | 0.3664 |
| retrieval_time | 0.0994 | 0.6139 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.4702 | 0.5417 | +0.0714 | +15.19% | 0.0018 | ✅ |
| mrr | 0.3035 | 0.3664 | +0.0629 | +20.73% | 0.0001 | ✅ |
| retrieval_time | 0.0994 | 0.6139 | +0.5146 | +517.75% | 0.0000 | ✅ |

## Winner

**Selected variant**: B
