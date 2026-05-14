# NEXT_PHASE_RECOMMENDATIONS.md — ResearchAgent

> For Hermes: use this as the next resumption guide after the cron pause. Continue with one smallest verified task per run: read relevant files, write a failing test first, verify failure, implement the minimum change, run targeted tests, then broader tests, then update status/work-log docs.

## Goal

Shift the project from “Phase 4 job-system micro-hardening” back toward the highest-value gaps for resume quality:
1. engineering credibility
2. product differentiation
3. delivery readiness

## Current recommendation order

### Priority 1 — CI verification and doc sync
Why first:
- `.github/workflows/tests.yml` already exists, so the highest-value remaining CI work is no longer file creation but truthful verification and delivery-surface alignment
- Latest locally verified full run is `192 passed, 1 skipped in 276.21s`
- Fastest path to convert current quality into externally visible engineering credibility is to prove and document the existing CI asset rather than keep hardening Phase 4 internals

Target outcome:
- Keep `.github/workflows/tests.yml` as the minimal GitHub Actions workflow
- Verify one real GitHub-hosted run on push / pull_request
- Sync README / EXECUTION_STATUS / DEVELOPMENT_LOG so they reflect that CI now exists in-repo
- Record remaining CI risks honestly (heavy dependencies, hosted-runner proof still pending until first real run)

Small-step execution hints:
1. Re-read `.github/workflows/tests.yml`, `README.md`, `requirements.txt`, and CI/status docs
2. Re-run `python -m pytest tests -q` in the project environment as the local compatibility baseline
3. Update stale docs that still imply CI is not started or still future work
4. If GitHub-side verification is unavailable in the current environment, label it explicitly as pending hosted-runner verification rather than claiming CI is fully proven
5. After doc sync, move to the next highest-value product gap

### Priority 2 — per-paper structured extraction
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
1. Phase 5.2 CI verification + doc sync
2. Phase 3.2 per-paper structured extraction
3. Phase 5.1 Dockerization
4. Phase 4.4 observability skeleton

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
