---
name: project-executor
description: Legacy compatibility alias for the older two-skill project flow. Use only when an existing prompt explicitly names `project-executor`; otherwise prefer `$project`, which creates, resumes, replans, validates, and closes long-running work through a single `docs/projects/PROJECT/tasks.md` tracker.
---

# Project Executor

## Overview

Legacy compatibility wrapper for the unified `$project` workflow.

## Preferred flow

- Prefer `$project` for all new usage.
- Keep one tracker at `docs/projects/<project>/tasks.md`.
- Use the unified template at `~/.agents/skills-source/owned/project/references/tasks-template.md` if the tracker needs normalization.

## Workflow

1. Read `Next 3 Actions`, `Progress Log`, `Open Questions / Blockers`, `Milestones`, and `Done When` first.
2. If the tracker is missing, incomplete, or stale, normalize it using the unified single-file structure before execution.
3. If project-critical ambiguity would likely stop long-horizon execution later, ask targeted follow-up questions before deep implementation.
4. Execute the next milestone or task batch, validate at logical checkpoints, and fix failures before advancing.
5. Keep updating tasks, milestones, decisions, blockers, progress, and next actions until the scoped work is complete or a real blocker remains.

## Output rules

- Keep `tasks.md` current alongside code changes.
- Prefer `$project` as the user-facing skill.
- Keep one primary orchestrator responsible for `tasks.md`.
- Keep summaries concise and include validation evidence plus remaining blockers or risks.
