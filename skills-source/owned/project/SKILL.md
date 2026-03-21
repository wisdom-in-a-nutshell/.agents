---
name: project
description: Create, resume, replan, and close long-running project work using a single tracker at `docs/projects/PROJECT/tasks.md`. Use when starting a new project, continuing an existing project, refreshing a stale plan, or asking an agent to handle a complicated multi-session task with durable repo memory, milestone validation, and a clear resume point.
---

# Project

## Overview

Use one project tracker file as the durable source of truth for long-running work. The skill decides whether to create, resume, replan, or close the tracker based on repo state, keeps that file current while it works, and archives finished projects by default when completion confidence is high.

## Default location

1. Check repo guidance (`AGENTS.md`, docs) for a prescribed location or format.
2. If none exists, use: `docs/projects/<project>/tasks.md`.
3. When archiving a finished project and no repo-local archive path is prescribed, use: `docs/projects/archive/<project>/tasks.md`.

## Workflow

1. **Locate the tracker**
   - If `docs/projects/<project>/tasks.md` is missing, create it using `references/tasks-template.md`.
2. **Choose the mode from repo state**
   - Missing tracker: create it.
   - Existing active tracker: resume from `Next 3 Actions`.
   - Existing tracker with stale or incorrect tasks: replan in place, then continue.
   - Fully complete tracker:
     - if sufficiently confident the scoped work is done, close it out and archive it immediately.
     - if material uncertainty remains, summarize the evidence and ask the user before archiving.
   - If archiving requires an archive folder that does not exist yet, create it as part of closeout.
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
   - If the current batch contains independent side work, multiple independent questions, or clearly separable implementation slices, you are encouraged to use subagents when that is likely faster or cleaner than staying single-threaded.
   - Let the model decide whether delegation helps; do not force subagents when local execution is faster or when the work is tightly coupled.
   - Prefer built-in `explorer` for local repo/runtime questions, managed `external_researcher` for information outside the repo/runtime, and built-in `worker` only for clearly isolated implementation slices with explicit ownership.
   - Treat `tasks.md` as the durable batch checkpoint: note what the parent thread is doing, what can be delegated, and what evidence or results need to be merged back before the next batch.
   - Keep one orchestrator responsible for the tracker and final synthesis.
6. **Execute**
   - Implement the next milestone or task batch directly.
   - Run validation from `Validation / Test Plan` or milestone-specific commands at logical checkpoints.
   - Prefer repo-native validation entrypoints first:
     - documented project check scripts from repo guidance,
     - otherwise `pre-commit run --all-files` when the repo uses pre-commit,
     - then task-specific tests, builds, or smoke checks required by the milestone.
   - Do not guess ad-hoc formatter or linter commands when the repo already defines a validation path.
   - If validation fails, fix forward before marking the milestone or task complete.
7. **Checkpoint after each meaningful batch**
   - Update milestone and task checkbox state.
   - Add a dated `Progress Log` entry.
   - Refresh `Decisions`, `Open Questions / Blockers`, and `Next 3 Actions`.
   - Merge results from any delegated subagent work back into the tracker before planning the next batch.
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
   - Follow repo-local shipping policy for commit/push behavior. Do not add a generic manual commit/push step when repo automation already handles it.
   - Archive by default when `Done When` is satisfied, remaining milestones/tasks are complete or explicitly descoped, validation is acceptable for the scoped work, and no material blocker remains.
   - Unless repo guidance says otherwise, archiving means moving the finished tracker from `docs/projects/<project>/tasks.md` to `docs/projects/archive/<project>/tasks.md`.
   - If `docs/projects/archive/` or `docs/projects/archive/<project>/` is missing, create it during closeout.
   - Ask the user before archiving only when project completion is materially uncertain or user intent appears to have shifted beyond the tracker.

## Tracker rules

- Keep `tasks.md` as the canonical active memory for the project.
- Keep durable execution state in the repo, not only in chat.
- Treat `tasks.md` as the durable coordination artifact for planning, checkpoints, and resume state.
- Use milestone-based execution with explicit acceptance criteria and validation.
- Default to long uninterrupted execution, not one-task-at-a-time reporting.
- Treat repo-local validation as authoritative; use `pre-commit` as the default baseline only when no stronger repo-local entrypoint is prescribed.
- Preserve a clear resume point in `Next 3 Actions`.
- Record non-obvious choices in `Decisions` so later agents do not reopen them.
- Treat blockers as first-class: add them to `Open Questions / Blockers` immediately.
- Bias toward finishing and archiving completed projects instead of leaving stale trackers in the active list.
- When a project is archived, prefer moving it into a dedicated archive path rather than only marking it archived in place, unless repo guidance explicitly prefers in-place archives.
- Do not introduce a `ready-to-archive` holding state by default.
- If subagents appear likely to improve speed or context hygiene, the top-level run is encouraged to use them for bounded, independent work.
- Subagents may read `tasks.md` for context, but the current top-level run remains the only writer.
- Do not let multiple agents edit `tasks.md` concurrently; treat it like a small coordination database that the parent thread updates at checkpoints.
- The current top-level run is the orchestrator; delegated agents return summaries, evidence, and next actions, and the parent thread merges those results into `tasks.md`.

## Closeout confidence test

- Archive without asking when all of the following are true:
  - `Done When` is satisfied.
  - Remaining milestones/tasks are either complete or explicitly descoped in the tracker.
  - Validation has passed, or any residual failure is documented as out of scope and non-blocking.
  - `Open Questions / Blockers` has no unresolved item that would change the deliverable if answered differently.
- Ask before archiving when any of the above is unclear or when closure depends on product judgment rather than implementation execution.

## Resources

- Use `references/tasks-template.md` when creating or normalizing `tasks.md`.
- The template defines the standard single-file long-horizon structure for goals, scope, milestones, validation, decisions, blockers, progress, and next actions.
- Create `docs/projects/<project>/resources/` only when the project produces reusable artifacts that help execution or verification: research notes, snapshots, generated fixtures, helper scripts, evaluation outputs, or logs worth keeping. Do not create it by default.
