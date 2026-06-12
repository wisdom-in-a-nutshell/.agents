# Project Tracker Operating Rules

Use this note when editing `tasks.md`, rebuilding `Current Batch`, checkpointing a long run, or deciding whether a tracker is ready to archive.

## Canonical Role Of `tasks.md`

- Treat `tasks.md` as the canonical project tracker and single durable resume point.
- Keep durable execution state in the repo, not only in chat.
- Use milestones for checkpoint-sized outcomes.
- Use `Current Batch` for active work now.
- Use `Backlog / Remaining Work` for work that is not active yet.

## When To Replan

Replan the tracker in place when any of these is true:

- `Current Batch` is empty
- `Current Batch` is stale or obviously wrong
- the scoped work shifted materially
- completed work is still marked active
- the remaining milestones or backlog no longer reflect reality

When replanning:

1. Rebuild `Current Batch` from the remaining milestones and backlog.
2. Keep shared-boundary work sequential.
3. Keep the live board small and concrete.
4. Promote only truly active work into `Current Batch`.

## How To Use `Current Batch`

- Treat `Current Batch` as the live execution board and primary resume point.
- Keep it small, usually `1-5` items total.
- Usually keep delegated items to `2-3` at once unless the work is mostly read-heavy.
- Keep one row per active parent-owned or delegated work item.
- Each row should say:
  - what is being done now
  - who owns it
  - whether a useful file exists in `resources/`

Recommended meanings for the columns:

- `Status`
  - `todo`, `in_progress`, `delegated`, `blocked`, or `done`
- `Work Item`
  - a concrete, scoped unit of work
- `Role`
  - `parent`, `explorer`, `external_researcher`, `worker`, or another explicit role when one exists
- `Resource`
  - a topic-based path under `resources/` when durable notes or artifacts exist

## Checkpoint Rules

Checkpoint after each meaningful batch:

1. Update milestone and task checkbox state.
2. Add a dated `Progress Log` entry.
3. Refresh `Decisions`, `Open Questions / Blockers`, `Current Batch`, and `Backlog / Remaining Work`.
4. Record the durable outcome of any delegated work in `tasks.md`.
5. Link topic-based files under `resources/` when durable notes, logs, or artifacts are worth keeping.
6. Reassess whether delegation is still helping.

Keep blockers first-class:

- Add them to `Open Questions / Blockers` immediately.
- Remove or resolve them as soon as the answer is known.

## Closeout And Archive Rules

- Archive by default when `Done When` is satisfied, remaining milestones/tasks are complete or explicitly descoped, validation is acceptable for the scoped work, and no material blocker remains.
- Ask before archiving only when project completion is materially uncertain or when closure depends on product judgment rather than implementation execution.
- Unless repo guidance says otherwise, archive by moving the tracker from the active tracker path to the repo's archive path, e.g. `projects/archive/<project>/tasks.md` or `docs/projects/archive/<project>/tasks.md`.
- If the archive folder does not exist, create it during closeout.
- Do not introduce a `ready-to-archive` holding state by default.

Archive without asking when all of the following are true:

- `Done When` is satisfied
- remaining milestones/tasks are complete or explicitly descoped
- validation has passed, or any residual failure is documented as out of scope and non-blocking
- `Open Questions / Blockers` has no unresolved item that would change the deliverable if answered differently

## `resources/` And `learnings/`

- Use `resources/` for durable working artifacts such as notes, logs, external research summaries, snapshots, or helper outputs.
- Keep `resources/` flat by default and use topic-based filenames.
- Do not name files after agent mechanics such as `subagent-batch-01.md`.
- Use `learnings.md` for project-specific retrospective notes about what would have made the run easier, faster, or more reliable.
- For long-running or tooling-heavy projects, add a backlog task to review and finalize `learnings.md` before archive.
