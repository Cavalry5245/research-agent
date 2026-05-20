# Experiment Report: prompt_comparison

Compare full 13-section note template (Variant A) vs compact 8-section template (Variant B).

## Variant Metrics

| Metric | Variant A | Variant B |
|---|---|---|
| content_length | 2994.0000 | 1945.0000 |
| generation_time | 4.4147 | 2.8708 |
| section_coverage | 0.8514 | 0.8924 |

## Deltas (B vs A) and Significance

| Metric | A | B | Δ | Relative | p-value | Significant |
|---|---|---|---|---|---|---|
| generation_time | 4.4147 | 2.8708 | -1.5439 | -34.97% | 0.0000 | ✅ |
| content_length | 2994.0000 | 1945.0000 | -1049.0000 | -35.04% | 0.0000 | ✅ |
| section_coverage | 0.8514 | 0.8924 | +0.0410 | +4.81% | 0.6985 | ❌ |

## Winner

**Selected variant**: B
