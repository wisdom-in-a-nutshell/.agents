# Dobby Context Maintenance

## Goal
Make Dobby conversations preserve memory before Codex context compaction across direct Codex and gateway surfaces.

## Why / Impact
Adi uses Dobby through both direct Codex desktop threads and the CodexClaw mobile gateway. Long Dobby conversations need automatic maintenance that keeps the live thread usable while preserving details that should become future Dobby memory.

## Scope / Non-Goals
### In Scope
- Repo-local Codex auto-compaction threshold policy for Dobby workspace repos.
- Dobby lifecycle `PreCompact` policy and recursion guard.
- Sidecar memory consolidation behavior around compaction boundaries.
- Later gateway maintenance triggers for token pressure, idle time, daily rollover, manual compact, and chat end.

### Out of Scope
- Global Codex auto-compaction defaults for unrelated repos.
- Replacing Codex App Server compaction internals.
- Reworking Dobby memory routing beyond the existing `dobby-workspace` body map.

## Context / Constraints
- Date started: 2026-05-16
- `model_auto_compact_token_limit` is an absolute token count, not a ratio.
- Local `gpt-5.5` model cache currently reports `context_window = 272000`; 75% is `204000`.
- User decision: leave global Codex defaults alone; apply repo-specific threshold only where needed.
- User decision: prefer the shared Dobby lifecycle / precompact model over a mobile-gateway-only token-delta design.
- `../adi/.codex/config.toml` and `../angie/.codex/config.toml` are generated from `~/.agents/codex/config/repo-bootstrap.json`; do not hand-edit them.
- Dobby lifecycle `PreCompact` is now wired as a best-effort sidecar launch; `consolidate-thread` remains the reusable memory-writing primitive.
- Sidecar consolidation should still get a recursion guard later, but the user chose to ship the basic path first.

## Done When
- [x] Dobby workspace repos have a repo-local Codex auto-compaction threshold around 75% of the active model context window.
- [x] Direct Codex Dobby threads have a safe precompact memory-preservation path.
- [ ] Gateway Dobby threads can use the same lifecycle primitive without racing live compaction.
- [ ] Sidecar consolidation cannot recursively trigger another consolidation from its own compaction.
- [x] Validation covers control-plane rendering and the critical lifecycle path.

## Milestones
- [x] Milestone 1 - Repo-local Codex threshold is rendered for Dobby workspaces. Acceptance: `adi` and `angie` repo configs include `model_auto_compact_token_limit = 204000`, globals remain unchanged. Validate: `./codex/scripts/check-codex-control-plane.sh`.
- [x] Milestone 2 - PreCompact policy is wired for Dobby workspaces. Acceptance: direct Codex compaction in `adi` enqueues memory work without blocking compaction. Validate: local hook smoke plus App Server compact smoke.
- [ ] Milestone 3 - Sidecar recursion guard is implemented. Acceptance: memory-consolidation sidecar compaction does not enqueue another memory-consolidation job. Validate: unit/smoke test with sidecar-labeled payload.
- [ ] Milestone 4 - Gateway maintenance is aligned to lifecycle. Acceptance: gateway compact/end/threshold paths trigger the shared maintenance primitive without reintroducing token-delta config. Validate: mobile-gateway tests and local gateway smoke.

## Execution Rules
- Keep global Codex defaults unchanged unless the user explicitly changes that decision.
- Keep repo-local generated `.codex/config.toml` files generated from `~/.agents`, not hand-edited.
- Keep slow memory synthesis out of inline hooks; hooks should capture/enqueue quickly.
- Keep one memory-writing primitive in Dobby lifecycle; gateway should own policy only where it is the caller.
- Update this tracker after each meaningful batch.

## Decisions
- Use `~/.agents` as the source of truth for Codex runtime/bootstrap policy.
- Use repo-local `model_auto_compact_token_limit` for Dobby workspace repos, not global config.
- Treat `204000` as the initial 75% threshold for current `gpt-5.5` context window (`272000`).
- Keep `consolidate-thread` sidecar-based. Ship PreCompact as a fail-open background launch first; add the recursion guard in a later batch.

## Open Questions / Blockers
- Need decide the exact sidecar recursion guard marker/skip condition: payload label, thread source kind, env flag, or config profile.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| done | Add and validate repo-local `model_auto_compact_token_limit` support and set `204000` for `adi`/`angie`. | parent | `/Users/dobby/.agents/codex/config/repo-bootstrap.json` |
| done | Wire and validate best-effort `PreCompact` sidecar launch for direct Codex threads. | parent | `/Users/dobby/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/pre-compact` |
| todo | Design and implement the sidecar recursion guard after the basic path has settled. | parent | `/Users/dobby/GitHub/adi/.agents/skills/dobby-lifecycle` |

## Backlog / Remaining Work
- [x] Wire `PreCompact` hook assignment for `adi` and `angie` after local App Server behavior is verified.
- [x] Add a fast hook path that enqueues memory work without doing slow synthesis inline.
- [ ] Add sidecar recursion guard and tests.
- [ ] Align CodexClaw gateway maintenance with the shared lifecycle primitive.
- [ ] Update lifecycle docs after behavior is proven.
- [ ] Review and finalize `docs/projects/dobby-context-maintenance/learnings/README.md` before archive.
- [ ] Archive the tracker when all milestones are complete.

## Validation / Test Plan
- `./codex/scripts/sync-repo-bootstrap-registry.py`
- `./codex/scripts/sync-repo-codex-configs.sh --check`
- `./codex/scripts/check-codex-control-plane.sh`
- Hook smoke for `PreCompact` in `../adi`
- App Server smoke for `thread/compact/start` in `../adi`
- Mobile-gateway affected tests when gateway behavior changes

## Progress Log
- 2026-05-16: [IN-PROGRESS] Created project tracker and started repo-local Codex threshold support.
- 2026-05-16: [DONE] Rendered `model_auto_compact_token_limit = 204000` for `adi` and `angie` only. `204000` is 75% of the current cached `gpt-5.5` context window (`272000`). Global Codex config remains unchanged. Validation passed: `python3 ./codex/scripts/sync-repo-bootstrap-registry.py`, `./codex/scripts/sync-repo-codex-configs.sh --check`, `python3 -m unittest tests.control_plane.test_codex_repo_sync`, and `./codex/scripts/check-codex-control-plane.sh --repo /Users/dobby/GitHub/adi --repo /Users/dobby/GitHub/angie`.
- 2026-05-16: [DONE] Wired `PreCompact` for `adi` and `angie` through existing `.agents` hook plumbing. The Dobby lifecycle hook writes a small job under `tmp/dobby-lifecycle/pre-compact/`, starts `consolidate-thread` in the background, and returns with no stdout so live compaction can continue. Validation passed: Dobby lifecycle tests, shared hook unit tests, full control-plane test suite, Codex control-plane check, direct dispatcher smoke, and App Server `thread/compact/start` smoke with a fake consolidation binary.
