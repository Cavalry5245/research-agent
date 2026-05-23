# Experiment Report: query_optimization

Compare original (A) vs LLM rewrite (B) vs HyDE (C) query strategies on retrieval quality.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.4702 | 0.5655 |
| latency | 0.0840 | 7.8714 |
| mrr | 0.3035 | 0.3450 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.4702 | 0.5655 | +0.0952 | +20.25% | 0.0001 | ✅ |
| mrr | 0.3035 | 0.3450 | +0.0416 | +13.70% | 0.0097 | ✅ |
| latency | 0.0840 | 7.8714 | +7.7875 | +9275.22% | 0.0000 | ✅ |

## Winner

**Selected variant**: B
