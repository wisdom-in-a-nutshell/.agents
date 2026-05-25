# Dobby lifecycle hooks

Lifecycle details live here so the shared `dobby-workspace` body map can stay
focused on workspace meaning instead of becoming a hook runbook.

## Simple lifecycle map

- `SessionStart`: read durable context and inject a compact boot packet into the
  active agent thread.
- `UserPromptSubmit`: add lightweight per-turn context when useful.
- Normal conversation/work happens in the live Codex thread.
- `finalize-codex-thread`: explicit end-of-thread command. It derives the repo
  from Codex App Server `thread/read`, asks the repo for a finalization
  instruction, runs one final turn in that same source thread, and archives only
  after that turn succeeds.
- `SessionEnd`: fast shutdown record only; it does not run memory work.
- Next `SessionStart`: recent `memory/sessions/...` notes return continuity to
  the next thread.

Short version:

- **SessionStart is read/inject.** It gathers the current Dobby context and gives
  the agent enough memory to continue well.
- **FinalizeCodexThread is explicit same-thread finalization.** The global
  `finalize-codex-thread` command is the public primitive. It runs repo policy
  from `scripts/hooks/finalize_codex_thread.py` when present.
- **Dobby finalization writes memory directly.** The repo hook emits the prompt
  for the final turn. That turn decides whether anything should be written under
  `memory/sessions/...`, `memory/now.md`, an area file, `soul.md`, or Shelf by
  reading the shared `dobby-workspace` body map.
- **Archive is conditional.** If the repo hook, final turn, or archive request
  fails, the source thread is left unarchived so stale cleanup can retry later.
- **SessionEnd is handoff-only.** It records shutdown metadata and exits quickly.
- **`memory/sessions` is the bridge.** End-of-thread notes become part of the
  next boot context.
- **`memory/now.md`, area files, and `soul.md` are promotion targets only.** They
  should be updated when something durable changes, not for every session.

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

- filename format: `memory/sessions/YYYY/MM/DD-HHMMSS.md` with numeric suffixes
  on collision
- shared body-map boot cap: 12000 chars
- boot context: last 3 notes plus notes from the last 7 days, capped at 10
- per-note boot cap: 2500 chars
- total recent-session boot block cap: 12000 chars

## Session notes

Session continuity lives in `memory/sessions/YYYY/MM/DD-HHMMSS.md`, not in
`memory/now.md`.

Stored notes stay plain prose. Do not add templates/frontmatter. Durable
decisions still get promoted to `now.md`, area canon, or `soul.md` as
appropriate.

## FinalizeCodexThread primitive

The global Codex control-plane finalizer is the preferred end-of-thread entry:

```bash
$HOME/.agents/codex/scripts/finalize-codex-thread.py \
  --thread-id <codex-thread-id> \
  --apply
```

Callers should pass only the thread id plus a reason label when useful. The
command uses `thread/read` as the source of truth for the current working
directory and repo root.

When a repo provides `scripts/hooks/finalize_codex_thread.py`, the finalizer runs
that script first. The script should print the instruction for the final turn to
stdout. The global finalizer then:

1. starts a new `turn/start` inside the original source thread;
2. waits for `turn/completed`;
3. archives the source thread through `thread/archive` only after success.

In Dobby workspaces the repo wrapper delegates to:

```bash
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/finalize-codex-thread
```

That hook emits a prompt asking the same live Dobby agent to preserve only
useful memory, using the shared body map as the routing authority. The hook does
not start Codex, fork a thread, write memory itself, or archive anything.

`SessionEnd` writes a compact record under `tmp/hooks/session-end/` and exits
successfully. It does not run memory work; end-of-thread memory work belongs to
explicit finalization.

Do not put Dobby memory synthesis directly in the shared `~/.agents` dispatcher.
The dispatcher routes lifecycle events; this skill owns Dobby-specific behavior.
