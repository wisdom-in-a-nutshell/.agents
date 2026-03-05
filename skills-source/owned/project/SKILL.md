---
name: project
description: Create, resume, replan, and close long-running project work using a single tracker at `docs/projects/PROJECT/tasks.md`. Use when starting a new project, continuing an existing project, refreshing a stale plan, or asking an agent to handle a complicated multi-session task with durable repo memory, milestone validation, and a clear resume point.
---

# Project

## Overview

Use one project tracker file as the durable source of truth for long-running work. The skill decides whether to create, resume, replan, or close the tracker based on repo state and keeps that file current while it works.

## Default location

1. Check repo guidance (`AGENTS.md`, docs) for a prescribed location or format.
2. If none exists, use: `docs/projects/<project>/tasks.md`.

## Workflow

1. **Locate the tracker**
   - If `docs/projects/<project>/tasks.md` is missing, create it using `references/tasks-template.md`.
2. **Choose the mode from repo state**
   - Missing tracker: create it.
   - Existing active tracker: resume from `Next 3 Actions`.
   - Existing tracker with stale or incorrect tasks: replan in place, then continue.
   - Fully complete tracker: summarize, ask for archive permission, and archive only after the user approves.
3. **Close critical gaps before deep execution**
   - If scope, success criteria, constraints, dependencies, credentials, or approvals are unclear enough that execution will predictably stall later, ask concise targeted follow-up questions before proceeding.
   - Batch missing items into one short request when possible.
   - Keep nudging until the tracker contains enough information for a long uninterrupted execution stretch.
   - Do not proceed on known project-critical ambiguity just because some implementation work is possible.
4. **Sync context**
   - Read `Next 3 Actions`, `Progress Log`, `Open Questions / Blockers`, `Milestones`, and `Done When` first.
   - Read only the code/docs named in `Context / Constraints` or recent progress before scanning the wider repo.
5. **Plan the next execution batch**
   - Work from `Next 3 Actions` first, then remaining milestones and tasks.
   - Keep shared-file or shared-contract work sequential.
   - Parallelize only truly independent tasks and keep one orchestrator responsible for the tracker.
6. **Execute**
   - Implement the next milestone or task batch directly.
   - Run validation from `Validation / Test Plan` or milestone-specific commands at logical checkpoints.
   - If validation fails, fix forward before marking the milestone or task complete.
7. **Checkpoint after each meaningful batch**
   - Update milestone and task checkbox state.
   - Add a dated `Progress Log` entry.
   - Refresh `Decisions`, `Open Questions / Blockers`, and `Next 3 Actions`.
   - Add newly discovered tasks when needed.
   - Continue if more actionable work remains.
8. **Run as a persistence loop**
   - Keep executing milestone-to-milestone until one of these stop conditions is true:
     - all scoped work is complete,
     - a real blocker requires human judgment, missing credentials, or external approval,
     - repo safety risk requires an explicit user decision.
   - Do not stop after one completed task or one validation pass when another actionable task remains.
9. **Closeout**
   - When scoped work is complete, provide a short conclusion with validation evidence and residual risks.
   - Ask for explicit permission before moving `docs/projects/<project>/` to `docs/projects/archive/<project>/`.

## Tracker rules

- Keep `tasks.md` as the canonical active memory for the project.
- Keep durable execution state in the repo, not only in chat.
- Use milestone-based execution with explicit acceptance criteria and validation.
- Default to long uninterrupted execution, not one-task-at-a-time reporting.
- Preserve a clear resume point in `Next 3 Actions`.
- Record non-obvious choices in `Decisions` so later agents do not reopen them.
- Treat blockers as first-class: add them to `Open Questions / Blockers` immediately.
- The current top-level run is the orchestrator; workers/background agents must not edit `tasks.md` directly.

## Resources

- Use `references/tasks-template.md` when creating or normalizing `tasks.md`.
- The template defines the standard single-file long-horizon structure for goals, scope, milestones, validation, decisions, blockers, progress, and next actions.
