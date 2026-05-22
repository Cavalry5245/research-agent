# Embedding Models Real Evaluation

Dataset: `app/evaluation/datasets/qa_eval_seed.jsonl` (168 samples)
Mode: simulated baseline (no live load)

## Per-Model Metrics

| Model | hit_at_5 | mrr | retrieval_time | live_avg_query_s |
|---|---|---|---|---|
| bge-small-zh-v1.5 | 0.7600 | 0.7000 | 0.2000 | - |
| bge-large-zh-v1.5 | 0.8200 | 0.7500 | 0.3200 | - |
| m3e-base | 0.7900 | 0.7200 | 0.2500 | - |

## Recommendation

**Highest hit_at_5**: `bge-large-zh-v1.5` (hit_at_5=0.8200)