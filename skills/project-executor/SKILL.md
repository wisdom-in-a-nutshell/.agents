---
name: project-executor
description: Resume and execute a long-running project based on docs/tasks/projects/PROJECT/tasks.md. Use when continuing work, implementing tasks, or updating progress across sessions. Read the tasks file, act on the next items, and keep tasks, progress log, and next actions current.
---

# Project Executor

## Overview
Continue a project by reading its `tasks.md`, executing the next actions, and keeping the file updated as the authoritative state.

## Default location
1. Check repo guidance (AGENTS.md, docs) for a prescribed location or format.
2. If none exists, use: `docs/tasks/projects/<project>/tasks.md`.

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
4. **Execute in order**
   - Work through Next 3 Actions, then continue down the Tasks list.
   - Make code changes when required by the task.
5. **Checkpoint after each task**
   - Check off completed tasks.
   - Add Progress Log entry: `YYYY-MM-DD: [DONE] task — outcome`
   - Refresh "Next 3 Actions" to reflect current state.
   - Add or refine tasks discovered during implementation.
6. **Handle blockers**
   - Add blockers to Open Questions and ask the user for direction.
   - Log as: `YYYY-MM-DD: [BLOCKED] task — what's blocking`

## Output rules
- Keep `tasks.md` current alongside code changes.
- If write access is not allowed, output the precise updates needed for `tasks.md`.
- When the project is complete, offer to commit and push the changes.
- Once the user confirms commit/push, run pre-commit checks and fix failures without asking again.
- Continue fixing and retrying commits until pre-commit checks pass, then push.
- After a successful push, ask whether to archive the project by moving it to `docs/tasks/projects/archive/<project>/` (create `archive/` if missing).

## Consistency rules
- Preserve required local sections if repo guidance mandates them.
- Keep tasks atomic and testable where applicable.
- If tasks.md is missing key sections (Goal, Why/Impact, Context, Validation), ask the user to run `$project-planner` to normalize it first.
- When making code changes, consider if `AGENTS.md` in affected folders needs updating or adding (new patterns, conventions, or guidance for future agents). If a task touches this, close it explicitly.
