# Retrieval Baseline Report

## Dataset Scale
- QA samples: 11
- Papers covered: 4
- Supporting-section labels: 6
- Dataset path: `app/evaluation/datasets/qa_eval_seed.jsonl`

## Retrieval Configuration
- Top-k: 3
- Retrieval mode: deterministic seed baseline
- Relevance rule: paper_id must match and section name must align with supporting_sections
- Source report: `app/evaluation/reports/retrieval_eval_seed_report.json`

## Metrics
- Hit@3: 1.000
- Recall@3: 1.000
- MRR: 1.000

## Failed Case Samples
### paper_20260509_004-abstract
- Query: What does the paper 'Receptive-Field and Direction Induced Attention' mainly propose or study?
- Hit@k: True
- Recall@k: 1.000
- MRR: 1.000
- Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
### paper_20260509_004-section-1
- Query: According to the 'results' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
- Hit@k: True
- Recall@k: 1.000
- MRR: 1.000
- Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
### paper_20260509_004-section-2
- Query: According to the 'INTRODUCTION' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
- Hit@k: True
- Recall@k: 1.000
- MRR: 1.000
- Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.

## Next-Step Recommendations
1. Replace the deterministic retrieval stub with the real vector-store retrieval pipeline before using these metrics as product KPIs.
2. Expand the seed dataset with more papers and harder multi-section questions to reduce metric inflation.
3. Add true negative and miss cases so failed-case analysis reflects real retriever behavior instead of placeholder calibration examples.

## Environment and Validation Notes
- Environment: WSL + conda
- Validation: Offline deterministic retrieval baseline; real retrieval chain not yet wired.
