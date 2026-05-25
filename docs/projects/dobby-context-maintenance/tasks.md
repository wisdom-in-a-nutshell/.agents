# Dobby Context Maintenance

## Goal
Make Dobby conversations preserve useful memory across direct Codex and gateway
surfaces without hidden sidecar complexity.

## Current Direction

As of 2026-05-25 this project has been simplified. The active architecture is:

- One explicit public primitive: `finalize-codex-thread`.
- Callers provide only the Codex thread id plus an optional reason label.
- The global finalizer reads the thread from Codex App Server, derives `cwd` and
  repo root, asks the repo for a final-turn instruction, runs that final turn in
  the same source thread, then archives only after success.
- Dobby workspaces provide repo policy through
  `scripts/hooks/finalize_codex_thread.py`, which delegates to the
  `dobby-lifecycle` skill hook.
- Native runtime hooks stay small: `SessionStart` and `UserPromptSubmit`.
- There is no managed fake/native-looking `SessionEnd`; official Codex hook
  docs do not expose that event, so end-of-thread work is explicit
  finalization.
- Gateway rollover and chat-end cleanup should call the same finalizer instead
  of running memory preservation directly.

The earlier sidecar-based design has been retired because it was hard to keep in
mind and introduced more moving parts than the reliability gain justified.

## Scope / Non-Goals

### In Scope

- Repo-local Codex boot/prompt/finalization context plumbing for Dobby workspace
  repos.
- Explicit same-thread finalization before archive.
- Gateway maintenance triggers for iPhone chat end and daily backend rollover.
- Durable docs/tests that make the architecture easy to rehydrate later.

### Out of Scope

- Global Codex auto-compaction defaults for unrelated repos.
- Replacing Codex App Server internals.
- Reworking Dobby memory routing beyond the existing `dobby-workspace` body map.

## Done When

- [x] Dobby workspace repos have repo-local Codex boot/prompt/finalization hooks.
- [x] The global stale-thread cleanup calls `finalize-codex-thread` for each old
  thread.
- [x] Dobby workspace finalization uses a same-thread final turn, not a side
  process.
- [ ] CodexClaw chat-end and daily rollover both use `finalize-codex-thread`.
- [ ] Validation covers control-plane rendering and the critical finalization
  path.
- [ ] Tracker is archived after CodexClaw and runtime rollout are verified.

## Execution Rules

- Keep global Codex defaults unchanged unless the user explicitly changes that
  decision.
- Keep repo-local generated `.codex/config.toml` and `.codex/hooks.json` files
  generated from `~/.agents`, not hand-edited.
- Keep native runtime hooks fast and deterministic.
- Use the thread id as the canonical finalization identity. Do not add parallel
  repo/directory sources of truth.
- Prefer clean cutovers over compatibility shims for this control-plane code.

## Current Batch

| Status | Work Item | Resource |
| --- | --- | --- |
| done | Replace Dobby repo finalization hook with `scripts/hooks/finalize_codex_thread.py`. | `/Users/dobby/GitHub/adi`, `/Users/dobby/GitHub/angie` |
| done | Rewrite global one-thread finalizer to run same-thread finalization before archive. | `/Users/dobby/.agents/codex/scripts/finalize-codex-thread.py` |
| done | Rename stale cleanup around finalization semantics. | `/Users/dobby/.agents/codex/scripts/finalize-stale-codex-threads.py` |
| done | Remove retired runtime memory-preservation hook from registry/tests/docs. | `/Users/dobby/.agents` |
| in_progress | Update CodexClaw gateway rollover/chat-end callers to use the global finalizer only. | `/Users/dobby/GitHub/codexclaw/services/mobile-gateway` |
| pending | Run full targeted validation and re-apply generated runtime hook state. | `.agents`, `adi`, `angie`, `codexclaw` |

## Validation / Test Plan

- `python3 -m py_compile` for changed Python entrypoints.
- `python3 -m unittest tests.control_plane.test_finalize_stale_codex_threads`
- `python3 -m unittest tests.control_plane.test_hooks_control_plane`
- `./scripts/test-control-plane.sh`
- `./scripts/check-agent-control-planes.sh`
- Dobby lifecycle skill tests.
- CodexClaw mobile-gateway tests and fast checks after gateway changes.

## Progress Log

- 2026-05-16: Started with repo-local Codex threshold and context-maintenance
  experiments for Dobby workspaces.
- 2026-05-18: Added gateway daily backend rollover for iPhone Dobby sessions.
- 2026-05-25: User pushed for a simpler mental model. Decision: retire the
  hidden side-process model and make `finalize-codex-thread` the single explicit
  primitive for end-of-thread memory preservation and archive.
- 2026-05-25: Removed the fake `SessionEnd` lifecycle surface. Current official
  Codex hook docs do not list `SessionEnd`, so Dobby uses only native
  `SessionStart`/`UserPromptSubmit` plus explicit `FinalizeCodexThread`.
