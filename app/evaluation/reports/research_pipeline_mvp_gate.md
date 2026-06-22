# MVP Gate Report - Research Pipeline

**Report Generated:** Not yet available (awaiting actual pipeline runs)

**Gate Status:** PENDING

## Summary

The evaluation harness is fully implemented and tested, but this MVP gate report requires actual research pipeline runs to evaluate. 

To generate a real gate report:

```bash
# 1. Create research runs using the seed questions
python -m app.research_pipeline.evaluation.run_mvp_gate \
  --db-path app/storage/research_pipeline.db \
  --run-ids <run_id_1> <run_id_2> <run_id_3>
```

## MVP Gate Conditions (PRD 10.3)

The gate checks the following conditions:

1. **Completion**: ≥2/3 seed questions reach "completed" status
2. **Time to report**: Median time < 300 seconds (5 minutes)
3. **Reader paper count**: Median ≥ 3 papers read per run
4. **Claim verification coverage**: Mean ≥ 60% of claims verified

## Seed Questions

Three seed research questions are available in:
`app/evaluation/datasets/research_pipeline_seed.jsonl`

Each question includes:
- 5 gold papers (with metadata)
- 5 gold report points (expected content)
- 5 gold claims (expected findings)

## Next Steps

1. Execute research pipeline runs for each seed question
2. Run the MVP gate report script with the resulting run IDs
3. This file will be replaced with the actual evaluation results

## Evaluation Infrastructure Status

✅ Seed dataset loader (27 tests passing)
✅ Evaluation metrics calculator (38 tests passing)
✅ MVP gate report generator (23 tests passing)
✅ Backend regression tests (370/370 passing)
✅ Frontend regression tests (93/93 passing)

**Total:** 551 tests passing across all components
