# Embedding Models Real Evaluation

Dataset: `app/evaluation/datasets/qa_eval_seed.jsonl` (168 samples)
Corpus: `app/storage/vector_db/vector_store.json` (860 chunks)
Mode: **live full** (real embeddings, paper-scoped retrieval, top_k=5)

## Per-Model Metrics

| Model | hit@5 | MRR | paper_recall | retrieval_time (s/q) | cache_reused |
|---|---|---|---|---|---|
| bge-small-zh-v1.5 | 0.4048 | 0.2780 | 1.0000 | 0.1145 | True |
| bge-large-zh-v1.5 | 0.4583 | 0.3008 | 1.0000 | 0.0580 | False |
| m3e-base | 0.5238 | 0.3460 | 1.0000 | 0.0166 | False |

## Recommendation

**Highest hit@5**: `m3e-base` (hit@5=0.5238, MRR=0.3460)

## Notes

- Section match is case-insensitive against `supporting_sections`.
- Retrieval is paper-scoped (filtered to `chunk.paper_id == sample.paper_id`), matching production behavior.
- `paper_recall` is a relaxed signal: 1.0 means the sample's paper is present in the corpus; metric is intended to surface data-coverage gaps when hit@5 looks low.
- If hit@5 is materially below `paper_recall`, the gap reflects section-level retrieval quality, not corpus coverage.