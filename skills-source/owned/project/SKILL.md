---
name: project
description: Create, resume, replan, and close long-running project work using the repo's project-tracker home (usually `docs/projects/PROJECT/tasks.md`, but follow repo guidance such as `projects/PROJECT/tasks.md` when specified). Use when starting a new project, continuing an existing project, refreshing a stale plan, or asking an agent to handle a complicated multi-session task with durable repo memory, milestone validation, and a clear resume point.
---

# Project

## Overview

Use one project tracker file as the durable source of truth for long-running work. Keep the tracker current while you work, execute from `Current Batch`, validate at milestone boundaries, and archive the tracker when the scoped work is genuinely done.

## Tracker Location

Follow repo-local guidance first.

1. If the repo defines a project-tracker home in `STRUCTURE.md`, `AGENTS.md`, or another root guidance file, use that.
   - Dobby workspace example: `projects/<project>/tasks.md` and `projects/archive/<project>/tasks.md`.
2. Otherwise use the default: `docs/projects/<project>/tasks.md`.
3. When archiving a finished project, archive under that same project-tracker home.

## Workflow

1. **Locate or create the tracker**
   - If the tracker is missing, create it with `references/tasks-template.md` in the repo's project-tracker home.
2. **Choose the operating mode from repo state**
   - Missing tracker: create it.
   - Active tracker: resume from `Current Batch`.
   - Stale or incorrect tracker: replan in place before continuing.
   - Finished tracker: archive it when completion is well supported; ask only when completion is materially uncertain.
3. **Close critical gaps before deep execution**
   - Ask concise follow-up questions when missing scope, success criteria, constraints, dependencies, credentials, or approvals would predictably stall the project later.
4. **Sync context from the tracker first**
   - Read `Current Batch`, `Milestones`, `Open Questions / Blockers`, `Progress Log`, and `Done When`.
   - Read only the files named by the tracker or recent progress before scanning wider repo context.
5. **Plan the next execution batch**
   - Rebuild `Current Batch` if it is empty, stale, or obviously wrong.
   - Freeze any moving shared contract or acceptance rule in the parent thread before delegating implementation.
   - Bias the first delegated pass toward read-heavy analysis, external verification, log triage, or isolated test work.
   - Delegate write-heavy implementation only when ownership, success criteria, and validation are clear.
   - Read `references/subagent-conventions.md` when delegation is likely or when deciding whether to collapse work back local.
   - Read `references/tracker-operating-rules.md` when editing tracker structure, rebuilding `Current Batch`, checkpointing, or closing out the project.
6. **Execute and validate**
   - Implement the next batch directly.
   - Run repo-native validation first, then milestone-specific tests or smokes.
   - Fix failures before marking milestone or task completion.
7. **Checkpoint**
   - Update the tracker after each meaningful batch.
   - Record delegated outcomes, decisions, blockers, resource files, and progress while the details are fresh.
8. **Persist until a real stop condition**
   - Continue until all scoped work is complete, a true blocker needs human input, or a repo-safety decision requires the user.
9. **Close out**
   - Summarize validation evidence and residual risks.
   - Include a short delegation retrospective when subagents were used.
   - Review and finalize `<project-root>/<project>/learnings.md` before archive for long-running or tooling-heavy projects.

## Core Rules

- Keep `tasks.md` as the canonical active memory for the project.
- Keep one orchestrator responsible for the tracker and final synthesis.
- Keep shared-boundary decisions in the parent thread.
- Use subagents only for bounded independent work; collapse back local when integration, validation orchestration, or runtime/device smoke work becomes dominant.
- Keep durable state in the repo, not only in chat.

## Resources

- Use `references/tasks-template.md` when creating or normalizing `tasks.md`.
- Use `references/tracker-operating-rules.md` for `Current Batch`, checkpoint, backlog, and closeout rules.
- Use `references/subagent-conventions.md` for delegation strategy, role split, split patterns, and anti-patterns.
- Use `references/learnings-template.md` when bootstrapping `<project-root>/<project>/learnings.md`.
