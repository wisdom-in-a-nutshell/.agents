---
name: project-executor
description: Resume and execute a long-running project based on docs/projects/PROJECT/tasks.md. Use when continuing work, implementing tasks, or updating progress across sessions. Read the tasks file, act on the next items, and keep tasks, progress log, and next actions current.
---

# Project Executor

## Overview
Continue a project by reading its `tasks.md`, executing the next actions, and keeping the file updated as the authoritative state using an execution/review/fix loop (not one-shot execution).

## Default location
1. Check repo guidance (AGENTS.md, docs) for a prescribed location or format.
2. If none exists, use: `docs/projects/<project>/tasks.md`.

## Workflow
1. **Locate and read the tasks file**
   - If missing, ask the user to run the planner skill first.
2. **Start at the resume point**
   - Read "Next 3 Actions" first — this is your starting point.
   - Scan Progress Log for recent state and any blockers.
   - Check Open Questions before starting if anything is unresolved.
3. **Sync context**
   - Read relevant code/docs mentioned in Context section.
   - Only scan the repo if Context doesn't give you enough to start.
4. **Execute a small batch in order**
   - Work through Next 3 Actions, then continue down the Tasks list.
   - Make code changes when required by the task.
   - Prefer small batches (usually 1-3 related tasks), then run the review loop before taking the next batch.
5. **Run a Ralph-style review loop**
   - Run validation commands from Validation / Test Plan (or closest package-scoped equivalent).
   - Self-review your own changes for correctness, regressions, edge cases, and contract drift.
   - For non-trivial or risky changes, request at least one additional agent review (local/cloud if available in the environment).
   - Apply feedback, rerun validation, and repeat until:
     - no unresolved high/medium-severity findings remain, and
     - validation passes (or known flakes are explicitly logged in Progress Log).
   - If review reveals more work, add/refine tasks before continuing.
6. **Checkpoint after each completed task/batch**
   - Check off completed tasks.
   - Add Progress Log entry: `YYYY-MM-DD: [DONE] task — outcome`
   - Refresh "Next 3 Actions" to reflect current state.
   - Add or refine tasks discovered during implementation.
   - If another task can be executed immediately, continue without waiting for user confirmation.
7. **Handle blockers**
   - Add blockers to Open Questions and ask the user for direction.
   - Log as: `YYYY-MM-DD: [BLOCKED] task — what's blocking`
8. **Run as a persistence loop**
   - Continue executing tasks until one of these stop conditions:
     - All scoped tasks are complete.
     - A true blocker requires human judgment/input/credentials.
     - Repo safety risk requires explicit user decision.
     - Additional iterations need product-level judgment instead of more implementation/review cycles.
   - Do not stop after a single completed task when additional actionable tasks remain.

## Output rules
- Keep `tasks.md` current alongside code changes.
- If write access is not allowed, output the precise updates needed for `tasks.md`.
- Rely on repository automation for commit/push when configured (for example notify hooks).
- In end-of-run summaries, include concise validation + review-loop evidence (what was checked, what was fixed, what remains).
- Before ending a run, ensure `tasks.md` has:
  - updated checkbox state,
  - fresh Progress Log,
  - clear Next 3 Actions or explicit completion note.
- Include concise evidence in summaries (file paths for major completed items and blockers).

## Consistency rules
- Preserve required local sections if repo guidance mandates them.
- Keep tasks atomic and testable where applicable.
- If tasks.md is missing key sections (Goal, Why/Impact, Context, Validation), ask the user to run `$project-planner` to normalize it first.
- When making code changes, consider if `AGENTS.md` in affected folders needs updating or adding (new patterns, conventions, or guidance for future agents). If a task touches this, close it explicitly.
- Prefer reasonable assumptions over pausing for minor ambiguities; only escalate when the decision is materially blocking or risky.
- Keep one primary executor responsible for `tasks.md`. If using extra/background agents, assign bounded sub-tasks and merge their findings back into the main loop.
- Do not run unbounded "background agents forever" loops.
