# Experiment Report: chunk_comparison

Compare chunk_size=800 / overlap=100 (A) vs chunk_size=500 / overlap=50 (B).

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| chunk_count | 18.0000 | 30.0000 |
| hit_at_3 | 0.7915 | 0.7971 |
| indexing_time | 3.7901 | 4.9738 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| chunk_count | 18.0000 | 30.0000 | +12.0000 | +66.67% | 0.0000 | ✅ |
| hit_at_3 | 0.7915 | 0.7971 | +0.0056 | +0.71% | 0.1581 | ❌ |
| indexing_time | 3.7901 | 4.9738 | +1.1838 | +31.23% | 0.0000 | ✅ |

## Winner

**Selected variant**: A
