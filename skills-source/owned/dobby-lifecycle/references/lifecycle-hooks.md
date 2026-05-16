# Dobby lifecycle hooks

Lifecycle details live here so the shared `dobby-workspace` body map can stay
focused on workspace meaning instead of becoming a hook runbook.

## Simple lifecycle map

```mermaid
flowchart TD
    A["SessionStart<br/>Dobby wakes up"] --> B["Read durable context"]
    B --> B1["soul.md<br/>identity + durable user truth"]
    B --> B2["dobby-workspace body map<br/>where things belong"]
    B --> B3["memory/now.md<br/>this week's orientation"]
    B --> B4["memory/sessions<br/>recent continuity notes"]
    B --> B5["Shelf + calendar + area manifest"]
    B --> C["Inject compact boot context<br/>into the active agent thread"]

    C --> D["Normal conversation / work"]

    D --> E{"Lifecycle save point"}
    E -->|Codex PostCompact| F["Write small job<br/>tmp/hooks/post-compact"]
    F --> G["consolidate-thread sidecar<br/>forks source Codex thread"]
    G --> H["Sidecar updates memory<br/>memory/sessions/YYYY/MM/DD-HHMMSS.md"]

    E -->|Codex SessionEnd| I["Write handoff record<br/>tmp/hooks/session-end"]

    H --> K["Next SessionStart loads recent notes<br/>so continuity comes back"]
```

Short version:

- **SessionStart is read/inject.** It gathers the current Dobby context and
  gives the agent enough memory to continue well.
- **PostCompact is write-back.** It preserves what would be lost by writing a
  compact session note under `memory/sessions/...`.
- **SessionEnd is handoff-only.** It records shutdown metadata without launching
  a second consolidation sidecar.
- **`memory/sessions` is the bridge.** End-of-session notes become part of the
  next boot context.
- **`memory/now.md`, area files, and `soul.md` are promotion targets only.**
  They should be updated when something durable changes, not for every session.

## Boot

Boot context is delivered by the repo's `SessionStart` hook
(`scripts/hooks/session_start.py`), which delegates to the skill-bundled hook.
The hook reads the shared `dobby-workspace` body map, `now.md`,
`state/shelf.json`, walks `memory/areas/`, reads recent session notes, and calls
the `dobby-calendar` skill CLI for upcoming events.

What boot context should include:

1. `soul.md` / identity context through the runtime system-prompt mechanism.
2. Shared `dobby-workspace/references/body-map.md` as the common Dobby body map.
3. `memory/now.md`.
4. Recent session notes: last 3 plus notes from the last 7 days, capped at 10.
5. Shelf snapshot.
6. Calendar snapshot for the next 2 days.
7. Area manifest.

Operational limits:

- filename format: `memory/sessions/YYYY/MM/DD-HHMMSS.md` with numeric suffixes on collision
- shared body-map boot cap: 12000 chars
- boot context: last 3 notes plus notes from the last 7 days, capped at 10
- per-note boot cap: 2500 chars
- total recent-session boot block cap: 12000 chars

## Session notes

Session continuity lives in `memory/sessions/YYYY/MM/DD-HHMMSS.md`, not in
`memory/now.md`.

## Consolidate-thread primitive

`scripts/hooks/consolidate-thread` is the reusable memory-consolidation
primitive.

It takes a source Codex/App Server thread, forks it into a sidecar thread, runs
a memory-consolidation prompt inside that sidecar, and lets the forked Dobby
agent update workspace memory directly.

It is intentionally policy-free:

- it does not compact the source thread
- it does not archive or delete the source thread
- it does not decide when cleanup should happen
- it does not use transcript summarization
- it may write `memory/sessions/...` and may promote durable facts according to
  the shared `dobby-workspace` body map

Supported direct invocation shape:

```bash
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/consolidate-thread \
  --workspace-root /Users/dobby/GitHub/adi \
  --thread-id <codex-thread-id>
```

Optional caller fields:

- `--source-turn-id <turn-id>`
- `--source-label <manual|post-compact|codexclaw-end-chat|...>`
- `--note-path <absolute-or-workspace-relative-path>`
- `--instruction <extra caller instruction>`
- `--job <payload.json>` for existing hook job records

PreCompact is intentionally not enabled for Dobby workspaces. For Codex runtimes, continuity finalization is owned by PostCompact. The
PostCompact hook records a small job under `tmp/hooks/post-compact/` and starts
`scripts/hooks/consolidate-thread` in the background. That worker starts a local
`codex app-server`, forks the source thread, injects a memory-consolidation
prompt that points to the shared `dobby-workspace` body map, and lets the forked
agent write directly to workspace memory. The worker starts its forked
app-server without special lifecycle environment flags for now. The Stop hook is
intentionally not disabled, so memory notes written by the sidecar can still be
committed by normal repo automation.

`DOBBY_CONSOLIDATE_THREAD_DISABLED=1` remains a manual kill switch to prevent
hooks from launching consolidation workers during debugging.

SessionEnd writes a compact record under `tmp/hooks/session-end/` and exits
successfully. It does not launch a consolidation sidecar because Codex
continuity is handled by PostCompact.

The PostCompact worker does not block session shutdown. If consolidation fails,
the worker logs to stderr/`tmp/hooks/session-finalizer/worker.log` and exits `0`.

Stored notes stay plain prose. Do not add templates/frontmatter. Durable
decisions still get promoted to `now.md`, area canon, or `soul.md` as
appropriate.

To temporarily prevent the Codex worker from launching from hooks, set
`DOBBY_CONSOLIDATE_THREAD_DISABLED=1`.

## Post-compaction hook

Repo-local `scripts/hooks/post_compact.py` wrappers delegate to the
skill-bundled `scripts/hooks/post-compact`. For Codex runtimes, this is the
simple sidecar design:

1. PostCompact writes one compact job record under `tmp/hooks/post-compact/`.
2. It starts `consolidate-thread` in the background.
3. The sidecar forks the source Codex thread.
4. The sidecar consolidates useful memory into `memory/sessions/...` and, when
   clearly warranted, the relevant promoted memory file.
5. Stop still runs normally and commits any resulting memory note.

Canonical IDs for PostCompact:

- `source_thread_id` — Codex/App Server thread being compacted
- `source_turn_id` — current turn if provided by the runtime

Do not put Dobby memory synthesis directly in the shared `~/.agents` dispatcher.
The dispatcher routes lifecycle events; this skill owns Dobby-specific behavior.
