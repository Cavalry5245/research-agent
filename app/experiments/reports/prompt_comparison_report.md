# Experiment Report: prompt_comparison

Compare full 13-section note template (Variant A) vs compact 8-section template (Variant B).

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| content_length | 4918.4444 | 4172.7778 |
| generation_time | 55.7230 | 52.3017 |
| section_coverage | 1.0000 | 1.0000 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| generation_time | 55.7230 | 52.3017 | -3.4213 | -6.14% | 0.0266 | ✅ |
| content_length | 4918.4444 | 4172.7778 | -745.6667 | -15.16% | 0.0002 | ✅ |
| section_coverage | 1.0000 | 1.0000 | +0.0000 | +0.00% | 0.5642 | ❌ |

## Winner

**Selected variant**: A
