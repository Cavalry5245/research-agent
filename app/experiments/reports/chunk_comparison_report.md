# Experiment Report: chunk_comparison

Compare chunk_size=800 / overlap=100 (A) vs chunk_size=500 / overlap=50 (B).

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| chunk_count | 860.0000 | 1318.0000 |
| hit_at_3 | 0.3214 | 0.3512 |
| indexing_time | 77.0900 | 68.3100 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| chunk_count | 860.0000 | 1318.0000 | +458.0000 | +53.26% | 0.0000 | ✅ |
| hit_at_3 | 0.3214 | 0.3512 | +0.0298 | +9.26% | 0.0798 | ❌ |
| indexing_time | 77.0900 | 68.3100 | -8.7800 | -11.39% | 0.0001 | ✅ |

## Winner

**Selected variant**: B
