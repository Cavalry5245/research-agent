# CI Implementation Plan

> For Hermes: use subagent-driven-development style execution with parallel specialist agents only where file ownership does not conflict. Controller must keep a live todo list, verify all worker claims independently, iterate review/fix loops until the CI strategy is trustworthy, then update status docs and cron prompt.

Goal: add a clean, deliverable CI workflow for ResearchAgent that runs the real Python test suite on GitHub Actions, documents the path clearly, and becomes a credible engineering asset within the project’s 24-hour delivery push.

Architecture:
- Keep CI minimal and repo-native: GitHub Actions on Ubuntu, Python 3.11, `pip install -r requirements.txt`, `python -m pytest tests -q`.
- Prefer the smallest correct workflow first, then harden docs and validation rather than overbuilding matrix/coverage/caching prematurely.
- Use controller + parallel subagents: one research/spec agent, one implementation agent, one review agent. Controller verifies all outputs with direct file reads, git diff, and local test execution.

Tech stack:
- GitHub Actions
- Python 3.11
- pytest
- Existing `requirements.txt`

Execution model constraints:
- Workdir: `/home/chase/projects/ResearchAgent`
- One smallest meaningful implementation step at a time
- TDD order when code/tests change
- Keep repo clean: no temp files, no dead files, no unnecessary folders
- After completion update:
  - `docs/EXECUTION_STATUS.md`
  - `docs/DEVELOPMENT_LOG.md`
  - `docs/CRON_WORK_LOG.md`
  - optionally `README.md` if CI usage/visibility changes materially

Task list for this wave:
1. Baseline and CI spec audit
2. Workflow design validation
3. Minimal workflow implementation
4. Local verification and review loop
5. Documentation sync
6. Cron prompt upgrade for orchestrated parallel execution
