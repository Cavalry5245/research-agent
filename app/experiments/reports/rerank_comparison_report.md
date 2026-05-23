# Experiment Report: rerank_comparison

Compare no-rerank (A) vs cross-encoder rerank with BAAI/bge-reranker-v2-m3 (B). Recall top_k=20, final top_k=5.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.4048 | 0.4821 |
| mrr | 0.2780 | 0.3162 |
| retrieval_time | 0.1049 | 0.6543 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.4048 | 0.4821 | +0.0774 | +19.12% | 0.0000 | ✅ |
| mrr | 0.2780 | 0.3162 | +0.0382 | +13.74% | 0.0240 | ✅ |
| retrieval_time | 0.1049 | 0.6543 | +0.5494 | +523.76% | 0.0000 | ✅ |

## Winner

**Selected variant**: B
