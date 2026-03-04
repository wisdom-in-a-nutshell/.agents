---
name: project-executor
description: Resume and execute a long-running project based on docs/projects/PROJECT/tasks.md. Use when continuing work, implementing tasks, or updating progress across sessions. Read the tasks file, act on the next items, and keep tasks, progress log, and next actions current.
---

# Project Executor

## Overview
Continue a project by reading its `tasks.md`, executing the next actions, and keeping the file updated as the authoritative state.

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
4. **Plan an execution batch**
   - Work from Next 3 Actions first, then continue down the Tasks list.
   - Group independent tasks into a batch when they can be parallelized safely.
   - Keep tasks sequential when they touch the same files/contracts or have dependency order.
5. **Execute the batch**
   - Run tasks directly when sequential.
   - If parallelizing, use one orchestrator + worker model:
     - Orchestrator assigns bounded sub-tasks.
     - Workers implement assigned sub-tasks and report outcomes.
     - Orchestrator integrates results and resolves conflicts.
   - Continue directly to the next actionable task without waiting for user confirmation between minor steps.
6. **Validate at logical checkpoints**
   - Run validation commands from Validation / Test Plan when relevant, or before marking a group of implementation tasks done.
   - If validation fails, fix forward and continue.
7. **Checkpoint after each completed task/batch**
   - Check off completed tasks.
   - Add Progress Log entry: `YYYY-MM-DD: [DONE] task — outcome`
   - Refresh "Next 3 Actions" to reflect current state.
   - Add or refine tasks discovered during implementation.
   - If another task can be executed immediately, continue without waiting for user confirmation.
8. **Handle blockers**
   - Add blockers to Open Questions and ask the user for direction.
   - Log as: `YYYY-MM-DD: [BLOCKED] task — what's blocking`
9. **Run as a persistence loop**
   - Continue executing tasks until one of these stop conditions:
     - All scoped tasks are complete.
     - A true blocker requires human judgment/input/credentials.
     - Repo safety risk requires explicit user decision.
   - Do not stop after a single completed task when additional actionable tasks remain.
   - Unless interrupted or blocked, keep working through the project continuously until completion.
10. **Closeout and archive decision**
   - When all scoped tasks are complete, first provide a short, plain-language conclusion to the user (what was done, validation status, and any residual risks).
   - Ask for explicit permission to archive.
   - Only move the project to `docs/projects/archive/...` after the user approves.

## Output rules
- Keep `tasks.md` current alongside code changes.
- Rely on repository automation for commit/push when configured (for example notify hooks).
- In end-of-run summaries, include concise validation evidence (what was checked, what was fixed, what remains).
- Before ending a run, ensure `tasks.md` has:
  - updated checkbox state,
  - fresh Progress Log,
  - clear Next 3 Actions or explicit completion note.
- Include concise evidence in summaries (file paths for major completed items and blockers).
- If completion is reached, include a simple conclusion, ask for archive permission, and wait for user approval before archiving.

## Consistency rules
- Preserve required local sections if repo guidance mandates them.
- Keep tasks atomic and testable where applicable.
- If tasks.md is missing key sections (Goal, Why/Impact, Context, Validation), ask the user to run `$project-planner` to normalize it first.
- When making code changes, consider if `AGENTS.md` in affected folders needs updating or adding (new patterns, conventions, or guidance for future agents). If a task touches this, close it explicitly.
- Prefer reasonable assumptions over pausing for minor ambiguities; only escalate when the decision is materially blocking or risky.
- Keep one primary executor (orchestrator) responsible for `tasks.md`.
- The current top-level Codex run (you, in the active session) is the orchestrator.
- Workers/background agents must not edit `tasks.md` directly; they report outcomes back to the orchestrator.
- Parallelize only independent tasks; avoid parallel edits to the same files/contracts unless the orchestrator is explicitly merging coordinated changes.
- Do not run unbounded "background agents forever" loops.
