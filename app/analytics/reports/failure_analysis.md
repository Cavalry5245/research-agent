# Failure Analysis Report

**Total failures**: 10

## Top Failure Modes

| Failure Type | Count |
|---|---|
| qa_low_score | 8 |
| qa_bad_citation | 1 |
| qa_empty_answer | 1 |

## Retrieval Failures

_None recorded._

## QA Failures

- Total: **10**
- Sub-types:
  - qa_bad_citation: 1
  - qa_low_score: 8
  - qa_empty_answer: 1
- Empty-answer failures: 2
- Long-answer failures (>800 chars): 0

## Comparison Failures

_None recorded._

## Optimization Suggestions

- Audit LLM error handling — empty answers often hide silent client closures.
- Tighten the QA prompt with explicit citation requirements and few-shot exemplars.
- Improve citation post-processing — verify each cited section actually appears in the retrieved chunks.