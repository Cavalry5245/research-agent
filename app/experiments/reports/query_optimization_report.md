# Experiment Report: query_optimization

Compare original (A) vs LLM rewrite (B) vs HyDE (C) query strategies on retrieval quality.

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| hit_at_5 | 0.7349 | 0.7642 |
| latency | 2.5379 | 3.0985 |
| mrr | 0.6673 | 0.7161 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| hit_at_5 | 0.7349 | 0.7642 | +0.0294 | +4.00% | 0.1101 | ❌ |
| mrr | 0.6673 | 0.7161 | +0.0488 | +7.32% | 0.0076 | ✅ |
| latency | 2.5379 | 3.0985 | +0.5606 | +22.09% | 0.0000 | ✅ |

## Winner

**Selected variant**: B
