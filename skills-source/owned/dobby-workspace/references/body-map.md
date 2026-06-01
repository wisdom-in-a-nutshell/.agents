# Dobby Workspace Body Map

A Dobby workspace is a personal-agent home: durable context, current orientation,
lived history, open loops, Dobby's own sharpening notes, lifecycle hooks, and
active improvement trackers.

## Core idea

Dobby wakes through a schema-backed nervous system:

```text
dobby/constitution.json
+ shared body map
+ memory/profile.json
+ memory/now.json
+ recent session-memory summaries
+ Shelf
+ calendar
+ memory/areas manifest
```

`dobby/constitution.json` is the prompt/instruction contract and may be loaded
directly by Codex as `model_instructions_file`. Person-specific context lives in
`memory/profile.json` and is loaded by lifecycle boot context.

## Organs

| Organ | Purpose |
|---|---|
| `dobby/constitution.json` | Dobby identity, mission, operating principles, boundaries, and memory/write-back policy. |
| `memory/profile.json` | Durable person-specific profile/context for the workspace. |
| `memory/` | Dobby's understanding: current orientation, area canon/logs, session memory. |
| `journal/` | Dated lived history: reflections, check-ins, raw captures, monthly synthesis. |
| `state/` | Live machine-readable state, usually Shelf. |
| `dobby/` | Dobby's operating contract and sharpening notes. |
| `projects/` | Active Dobby/app/system improvement trackers. |
| `scripts/` | Repo-local checks, lifecycle wrappers, and local helpers. |
| `.agents/skills/` | Repo-local links to operational skills. |
| `.codex/` | Runtime/tooling configuration. |
| `.antigravitycli/` | Local Antigravity CLI experiment/runtime state; not Dobby memory. |
| `tmp/` | Disposable scratch and hook logs. |

## Routing table

| Content | Canonical home |
|---|---|
| Dobby behavior / constitution / boundaries | `dobby/constitution.json` |
| Durable person profile / preferences / values / patterns | `memory/profile.json` |
| Shared workspace body meaning | `dobby-workspace` skill |
| This week's active orientation | `memory/now.json` |
| Area-specific durable understanding | `memory/areas/<area>/canon.json` |
| Area-specific dated fact/event | `memory/areas/<area>/log.jsonl` |
| Area metadata, assets, data dirs | `memory/areas/<area>/area.json` |
| Session memory record | `memory/sessions/YYYY/MM/DD-HHMMSS.json` |
| Reflection / check-in / raw capture | `journal/daily/YYYY-MM-DD/{morning,night,general}.json` |
| Monthly synthesis / templates | `journal/monthly/**/*.json`, `journal/templates/**/*.json` |
| Personal actionable open loop | `state/shelf.json` via `dobby-shelf` |
| Dobby/agent work tracker | `projects/<project>/tasks.md` |
| Dobby's own high-bar behavioral corrections, blindspots, operational instincts, and promotions | `dobby/growth.jsonl` |
| Exact command/schema/operational recipe | Relevant skill under `~/.agents/skills-source/owned/` |
| Antigravity CLI runtime/experiment state | `.antigravitycli/` |
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
the skills that write the data where possible. Cross-cutting workspace schemas
such as `dobby/constitution.json`, `memory/profile.json`, `memory/now.json`,
area metadata/canon/logs, and `dobby/growth.jsonl` are enforced by the shared
workspace linter.

## Memory contract

- `dobby/constitution.json` is one path-addressable JSON file for Dobby behavior.
- `memory/profile.json` is one path-addressable JSON file for person context.
- `memory/now.json` is the short active weekly/current-orientation layer.
- Area canon files hold durable domain understanding: `memory/areas/<area>/canon.json`.
- Area logs are append-only JSONL dated facts/events: `memory/areas/<area>/log.jsonl`.
- Area metadata and non-text assets are indexed through `memory/areas/<area>/area.json`.
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

1. Confirm the desired body change with the relevant human or an existing
   explicit project tracker decision.
2. Update this shared body map and `scripts/lint-workspace` together.
3. Keep lifecycle behavior in `dobby-lifecycle`, not here.
