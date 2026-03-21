# Project Subagent Conventions

Use this note as the project-specific subagent playbook for the current control plane. It complements the main `project` skill instead of repeating the full OpenAI subagent docs.

## Available Roles In This Setup

- `parent`
  - the top-level run
  - owns planning, orchestration, checkpointing, and the canonical tracker
- `explorer`
  - built-in read-heavy codebase and runtime exploration
  - use for inside-the-repo questions
- `external_researcher`
  - managed custom role for information outside the local repo and runtime
  - use for official docs, external APIs, current facts, MCP-backed lookups, and outside-world verification
- `worker`
  - built-in execution-focused role
  - use only for clearly isolated implementation slices with explicit ownership

## When To Use Subagents

Use subagents when at least one of these is true:

- the current batch has multiple independent questions that can be answered in parallel
- the work naturally splits into local exploration, outside verification, and implementation
- delegating noisy work would keep the parent thread cleaner and easier to reason about
- the task is large enough that waiting on one long read-heavy pass would slow everything down

Keep the work local when:

- the next action is urgent and delegation would block progress
- the work is tightly coupled across the same files or contract
- the task is small enough to finish directly in one pass
- coordination cost is likely higher than the speedup

## Project Rules

- `tasks.md` is the canonical project tracker and remains single-writer.
- The parent thread owns `Current Batch`, milestone state, backlog state, blockers, and closeout.
- Subagents may read `tasks.md` for context.
- Subagents may write topic-based notes or artifacts under `docs/projects/<project>/resources/` when durable working memory is useful.
- Before delegated work starts, the parent thread should add or refresh the corresponding row in `Current Batch`.
- The parent thread records the durable outcome of delegated work in `tasks.md`.

## How To Use `Current Batch`

Treat `Current Batch` as the live execution board.

- Keep it small, usually `1-5` items total.
- Usually keep delegated items to `2-3` at once unless the work is mostly read-heavy.
- Keep one row per active parent-owned or delegated work item.
- Each row should say what is being done now, who owns it, and whether there is a useful file in `resources/`.
- Move completed, stale, or blocked items out during checkpoints.
- If the board is empty or stale, rebuild it from `Milestones` and `Backlog / Remaining Work` before continuing.
- Promote work from `Backlog / Remaining Work` into `Current Batch` only when it is truly active.

Recommended meanings for the columns:

- `Status`
  - `todo`, `in_progress`, `delegated`, `blocked`, `done`
- `Work Item`
  - a concrete, scoped unit of work
- `Role`
  - `parent`, `explorer`, `external_researcher`, `worker`, or another explicit role when one exists
- `Resource`
  - a topic-based path under `resources/` when durable notes or artifacts exist

## How To Use `resources/`

Keep `resources/` simple by default.

- Use topic-based filenames such as `auth-flow.md`, `api-notes.md`, or `settings-save-root-cause.md`.
- Do not name files after agent mechanics such as `subagent-batch-01.md`.
- Keep the folder flat unless the project has enough material to justify subfolders.
- Use it for durable notes, logs, external research summaries, snapshots, helper outputs, and other artifacts worth preserving across sessions.

## Recommended Split Patterns

- `explorer` + `external_researcher`
  - use when you need local code understanding plus outside verification
- multiple `explorer` runs
  - use when there are several independent codebase questions
- `explorer` then `worker`
  - use when implementation should wait until the local execution path is understood
- `external_researcher` then `worker`
  - use when implementation depends on confirming external behavior first

## Anti-Patterns

- letting multiple agents edit `tasks.md`
- splitting work that touches the same contract or file cluster without clear ownership
- delegating tiny tasks that the parent thread could finish immediately
- filling `Current Batch` with backlog items instead of active work
- turning `resources/` into an unstructured dump of raw output

## Why This Shape

This setup follows the main ideas from the OpenAI subagent guidance:

- use subagents explicitly, not by accident
- prefer read-heavy parallelism first
- keep the parent thread focused on orchestration and final synthesis
- avoid unnecessary context pollution in the main thread
- be conservative with write-heavy parallel work
