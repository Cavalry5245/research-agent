# Milestone 2: Zotero Collection to Local Paper Processing

## Scope

Execute the implementation plan in:

`docs/superpowers/plans/2026-06-09-zotero-collection-processing.md`

Goal: make ResearchRun process a Zotero collection into local parsed/indexed papers and per-paper Knowledge Pack notes with item-level status tracking.

## Constraints

- Do not modify `.env` without explicit user approval.
- Do not bulk delete files or directories.
- Do not delete datasets, checkpoints, outputs, logs, or experiment results.
- Work one task at a time.
- Keep changes scoped to the files listed in the plan.
- Do not revert unrelated dirty worktree changes.
- After each task, run the task-specific verification command and inspect `git diff`.

## Tasks

1. Add item-level Research Run schemas.
2. Add Zotero collection intake service.
3. Add local paper processing service.
4. Update Knowledge Pack summary, trace, and tool calls.
5. Orchestrate local collection execution.
6. Add API endpoint for local execution.
7. Update Streamlit Research Workflow UI.
8. Run Milestone 2 verification and update execution docs.
