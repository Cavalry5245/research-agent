> **[已归档 - 2026-05-18]** 本计划已被 JD_ALIGNED_ROADMAP.md 替代。  
> 保留此文档作为历史记录和参考。  
> 新执行计划：[JD_ALIGNED_ROADMAP.md](../JD_ALIGNED_ROADMAP.md)

# NEXT_PHASE_RECOMMENDATIONS.md — ResearchAgent

> For Hermes: use this as the next resumption guide after the cron pause. Continue with one smallest verified task per run: read relevant files, write a failing test first, verify failure, implement the minimum change, run targeted tests, then broader tests, then update status/work-log docs.

## Goal

Shift the project from “Phase 4 job-system micro-hardening” back toward the highest-value gaps for resume quality:
1. engineering credibility
2. product differentiation
3. delivery readiness

## Current recommendation order

### Priority 1 — Phase 3.2 compare/extraction contract hardening
Why first:
- GitHub-hosted CI proof remains externally blocked by missing `gh` / hosted-runner access, so repeating CI-only doc sync has hit diminishing returns for local autonomous runs
- `paper_compare.py` already contains a working two-stage structured extraction + compare flow, making the highest-value local task no longer “start extraction” but “tighten its contracts against messy LLM payloads”
- Small compare/extraction contract upgrades are low-conflict, easy to verify with focused tests, and improve the project’s product differentiation story faster than more CI narration churn
- Latest locally verified full run is `202 passed, 1 skipped in 8.93s`

Target outcome:
- Keep the existing two-stage compare pipeline in `app/services/paper_compare.py`
- Add one smallest contract test at a time around malformed compare/extraction payloads
- Normalize or safely drop invalid compare-stage evidence / per-paper fields instead of crashing
- Keep docs truthful that Phase 3.2 is partially completed in-place, while GitHub-hosted CI proof is still pending external verification

Small-step execution hints:
1. Re-read `app/services/paper_compare.py`, `tests/test_paper_compare.py`, and status docs
2. Add one failing focused test for the next malformed payload shape
3. Implement the minimum normalization / fallback logic
4. Re-run `python -m pytest tests/test_paper_compare.py -q`, then the related compare/index regression set, then full suite if the change touches shared contracts
5. Update docs to reflect the newest local baseline and keep CI as a blocked external verification lane, not the main local coding lane

### Priority 2 — CI verification and doc sync
Why second:
- `.github/workflows/tests.yml` already exists and local compatibility has been repeatedly re-proven
- The remaining highest-value CI gap is one real GitHub-hosted run, but that evidence is still blocked in the current environment
- CI docs still need truthful maintenance, but they should no longer crowd out the smallest code-level product improvement each run

Target outcome:
- Keep `.github/workflows/tests.yml` as the minimal GitHub Actions workflow
- Verify one real GitHub-hosted run on push / pull_request when access becomes available
- Sync README / EXECUTION_STATUS / DEVELOPMENT_LOG so they reflect current local proof and honest hosted-runner uncertainty
- Record remaining CI risks honestly (heavy dependencies, hosted-runner proof still pending until first real run)

Small-step execution hints:
1. Re-read `.github/workflows/tests.yml`, `README.md`, `requirements.txt`, and CI/status docs
2. Re-run `python -m pytest tests -q` in the project environment as the local compatibility baseline when doc truthfulness changes
3. Update stale docs that still imply CI is not started or still future work
4. If GitHub-side verification is unavailable in the current environment, label it explicitly as pending hosted-runner verification rather than claiming CI is fully proven
5. After doc sync, return to the next smallest product gap instead of repeating CI-only narration

### Priority 3 — per-paper structured extraction modularization
Why second:
- Biggest remaining product differentiation gap in Phase 3
- Bridges the current gap between “structured compare schema exists” and “comparison pipeline has a clearly explainable architecture”
- Makes the project much easier to describe in interviews: extract structured fields per paper, then align across papers with evidence

Target outcome:
- Add `app/services/paper_extractor.py`
- Add `tests/test_paper_extractor.py`
- Extract at least the fields already present in comparison schema, using minimal deterministic / existing-LLM-backed approach consistent with current codebase
- Integrate extraction into comparison flow without overbuilding

Small-step execution hints:
1. Start with one smallest field-extraction contract test
2. Add minimal extractor object/function
3. Add one integration test into compare path
4. Expand field coverage incrementally
5. Update docs and evaluation notes

### Priority 3 — Dockerization
Why third:
- Strong delivery asset, but more environment-sensitive than CI
- Good after CI documentation and verification are aligned so the project already has a visible quality gate

Target outcome:
- Add `Dockerfile`
- Optionally add `docker-compose.yml`
- Add `.dockerignore`
- Provide documented local run path even if full Docker verification is blocked by missing local Docker

### Priority 4 — observability skeleton
Why fourth:
- Important for engineering depth
- Less immediately visible than CI / compare architecture improvements
- Best implemented after current core feature and delivery gaps are tightened

Target outcome:
- Add minimal structured logging and timing hooks
- Prefer small, testable observability helpers over ambitious telemetry systems

## Recommended execution path

If resuming immediately, choose this sequence:
1. Phase 3.2 compare/extraction contract hardening
2. Phase 5.2 CI verification + doc sync when hosted-runner access is available
3. Phase 3.2 per-paper structured extraction modularization
4. Phase 5.1 Dockerization
5. Phase 4.4 observability skeleton

## Why not continue job lifecycle micro-contract work right now

The project already has strong evidence of Phase 4 job-system progress:
- lifecycle schema hardening
- `/jobs` and `/jobs/{job_id}`
- `JobStore` seam
- `FileJobStore`
- env-driven store switching
- file-backed submission regression coverage

Additional tiny job-contract hardening is now likely lower ROI than:
- CI verification and visibility
- extractor architecture for product differentiation
- Docker for delivery readiness

## Resume checklist

Before the next implementation run:
- keep cron paused unless explicitly resumed
- keep workdir at `/home/chase/projects/ResearchAgent`
- follow `docs/HERMES_EXECUTION_PLAN.md`
- enforce one smallest meaningful task per run
- do TDD in strict order
- update:
  - `docs/EXECUTION_STATUS.md`
  - `docs/DEVELOPMENT_LOG.md`
  - `docs/CRON_WORK_LOG.md`
