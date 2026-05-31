# Dobby Workspace Body Map

A Dobby workspace is not a normal software repository. It is a personal-agent
home: durable context, current orientation, lived history, open loops, Dobby's
own sharpening notes, lifecycle hooks, and active improvement trackers.

## Core idea

Dobby wakes through a nervous system:

```text
soul.md
+ shared body map
+ memory/now.md
+ recent session-memory summaries
+ Shelf
+ calendar
+ memory/areas manifest
```

## Organs

| Organ | Purpose |
|---|---|
| `soul.md` | Constitution: Dobby identity, durable user truth, values, boundaries. |
| `memory/` | Dobby's understanding: current orientation, area canon/logs, session memory. |
| `journal/` | Dated lived history: reflections, check-ins, raw captures, monthly synthesis. |
| `state/` | Live machine-readable state, usually Shelf. |
| `dobby/` | Dobby's own sharpening notes and blindspot record. |
| `projects/` | Active Dobby/app/system improvement trackers. |
| `scripts/` | Repo-local checks, lifecycle wrappers, and local helpers. |
| `.agents/skills/` | Repo-local links to operational skills. |
| `.codex/` | Runtime/tooling configuration. |
| `tmp/` | Disposable scratch and hook logs. |

## Routing table

| Content | Canonical home |
|---|---|
| Dobby constitution / durable user truth | `soul.md` |
| Shared workspace body meaning | `dobby-workspace` skill |
| This week's active orientation | `memory/now.md` |
| Area-specific durable understanding | `memory/areas/<area>/<area>.md` |
| Area-specific dated fact/event | `memory/areas/<area>/log.md` |
| Session memory record | `memory/sessions/YYYY/MM/DD-HHMMSS.json` |
| Reflection / check-in / raw capture | `journal/daily/YYYY-MM-DD/{morning,night,general}.json` |
| Monthly synthesis | `journal/monthly/...` |
| Personal actionable open loop | `state/shelf.json` via `dobby-shelf` |
| Dobby/agent work tracker | `projects/<project>/tasks.md` |
| Dobby's own behavioral sharpening | `dobby/growth.md` |
| Exact command/schema/operational recipe | Relevant skill under `~/.agents/skills-source/owned/` |
| Temporary scratch / hook logs | `tmp/` |

One fact should have one canonical home. If another place needs awareness, point
to the canonical home instead of duplicating.

## Validation contract

Whatever can be mechanically enforced should be enforced by validators, not by
long prompt prose.

```text
repo scripts/check-fast.sh
  -> dobby-workspace/scripts/validate
       -> dobby-workspace/scripts/lint-workspace
       -> dobby-lifecycle/scripts/validate
       -> journal-checkin/scripts/validate
       -> dobby-shelf/scripts/validate
```

`dobby-workspace` owns orchestration and body shape. Domain schemas stay with
the skills that write the data.

## Memory contract

- `memory/now.md` is the short active weekly layer.
- Area canon files hold durable domain understanding.
- Area logs are append-only dated facts: `- YYYY-MM-DD — <event>`.
- Session memory records are continuity index cards, not canon by default.
  V2 records use `title`, Markdown `summary`, `threadId`, `trigger`, and
  Markdown/plain-English `workspaceChanges`; the `summary` field is the boot
  surface and `threadId` points back to the source transcript when needed.
- Personal open loops never live in memory; they live in Shelf.
- Raw reflections live in journal first and only become memory after synthesis.
- Daily journal storage is JSON-only: structured check-ins use `morning.json`
  and `night.json`; flexible captures append to `general.json.entries[]`.

## Change protocol

When a workspace shape change is intentional:

1. Ask the relevant human whether the workspace body should change.
2. Update this shared body map and `scripts/lint-workspace` together.
3. Keep lifecycle behavior in `dobby-lifecycle`, not here.
