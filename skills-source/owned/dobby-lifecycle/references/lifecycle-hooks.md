# Dobby lifecycle hooks

Lifecycle details live here so `STRUCTURE.md` can stay the workspace body map
instead of becoming a hook runbook.

## Boot

Boot context is delivered by the repo's `SessionStart` hook
(`scripts/hooks/session_start.py`), which delegates to the skill-bundled hook.
The hook reads `STRUCTURE.md`, `now.md`, `state/shelf.json`, walks
`memory/areas/`, reads recent session notes, and calls the `dobby-calendar`
skill CLI for upcoming events.

What boot context should include:

1. `soul.md` / identity context through the runtime system-prompt mechanism.
2. `STRUCTURE.md` as the Dobby workspace body map and routing contract.
3. `memory/now.md`.
4. Recent session notes: last 3 plus notes from the last 7 days, capped at 10.
5. Shelf snapshot.
6. Calendar snapshot for the next 2 days.
7. Area manifest.

Operational limits:

- filename format: `memory/sessions/YYYY/MM/DD-HHMMSS.md` with numeric suffixes on collision
- structure boot cap: 16000 chars
- boot context: last 3 notes plus notes from the last 7 days, capped at 10
- per-note boot cap: 2500 chars
- total recent-session boot block cap: 12000 chars

## Session notes

Session continuity lives in `memory/sessions/YYYY/MM/DD-HHMMSS.md`, not in
`memory/now.md`. Repo-local `scripts/hooks/session_end.py` wrappers delegate to
the skill-bundled `scripts/hooks/session-end`, which keeps shutdown fast by
writing a handoff record under `tmp/hooks/session-end/`, launching a background
continuity worker, and exiting `0`.

For Codex runtimes, `scripts/hooks/codex-finalize-session` starts local
`codex app-server`, forks the source thread, injects a finalization prompt that
points to `STRUCTURE.md`, and lets the forked agent write directly to
`memory/sessions/...`. This is the preferred path because it reuses the source
thread context and keeps the active user thread clean.

For non-Codex runtimes, `scripts/hooks/write-session-note` is the legacy
transcript path. It renders the transcript when the runtime provides
`transcript_path`, passes it to a note-generation placeholder, and writes one
new note when a generator returns text.

Neither worker blocks session shutdown. If finalization fails, the worker logs
to stderr/`tmp/hooks/session-finalizer/worker.log` for Codex or
`tmp/hooks/session-memory/worker.log` for the legacy worker and exits `0`.

Stored notes stay plain prose. Do not add templates/frontmatter. Durable
decisions still get promoted to `now.md`, area canon, or `soul.md` as
appropriate.

For smoke tests of the legacy worker only, `DOBBY_SESSION_MEMORY_FAKE_NOTE` or
`--fake-note` can supply the note body. To temporarily prevent the Codex worker
from launching from hooks, set `DOBBY_CODEX_FINALIZER_DISABLED=1`.

## Pre-compaction hook

Repo-local `scripts/hooks/pre_compact.py` wrappers delegate to the
skill-bundled `scripts/hooks/pre-compact`. The hook is intentionally quiet: it
writes a compact lifecycle record under `tmp/hooks/pre-compact/`, starts the
same Codex finalizer in the background when a Codex source thread id is
available, and prints nothing to stdout.

Canonical IDs:

- `source_thread_id` — Codex/App Server thread being compacted
- `source_turn_id` — current turn if provided by the runtime

Do not put Dobby memory synthesis directly in the shared `~/.agents` dispatcher.
The dispatcher routes lifecycle events; this skill owns Dobby-specific behavior.
