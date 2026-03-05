---
name: project-planner
description: Legacy compatibility alias for the older two-skill project flow. Use only when an existing prompt explicitly names `project-planner`; otherwise prefer `$project`, which creates, resumes, replans, validates, and closes long-running work through a single `docs/projects/PROJECT/tasks.md` tracker.
---

# Project Planner

## Overview

Legacy compatibility wrapper for the unified `$project` workflow.

## Preferred flow

- Prefer `$project` for all new usage.
- Keep one tracker at `docs/projects/<project>/tasks.md`.
- Use the unified template at `~/.agents/skills-source/owned/project/references/tasks-template.md` when creating or normalizing a tracker.

## Workflow

1. Identify the project and create or refresh `docs/projects/<project>/tasks.md`.
2. If project-critical information is missing and later execution would predictably stall, ask targeted follow-up questions before finalizing the tracker.
3. Populate the tracker using the unified single-file structure: goal, scope, context, done-when, milestones, execution rules, decisions, blockers, tasks, validation, progress, and next actions.
4. Offer to continue immediately with `$project`.

## Output rules

- Write or update `tasks.md` directly.
- Prefer `$project` as the next handoff, not `$project-executor`.
- Keep the tracker detailed enough that a later agent can resume cold.

## Resources

- Use `references/tasks-template.md` in this folder only for legacy compatibility.
- The canonical template now lives at `~/.agents/skills-source/owned/project/references/tasks-template.md`.
