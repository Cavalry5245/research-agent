# Experiment Report: query_optimization

Compare original (A) vs LLM rewrite (B) vs HyDE (C) query strategies on retrieval quality.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.4048 | 0.5417 |
| latency | 0.0892 | 3.4811 |
| mrr | 0.2780 | 0.3255 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.4048 | 0.5417 | +0.1369 | +33.82% | 0.0000 | ✅ |
| mrr | 0.2780 | 0.3255 | +0.0475 | +17.09% | 0.0056 | ✅ |
| latency | 0.0892 | 3.4811 | +3.3919 | +3801.64% | 0.0000 | ✅ |

## Winner

**Selected variant**: B
