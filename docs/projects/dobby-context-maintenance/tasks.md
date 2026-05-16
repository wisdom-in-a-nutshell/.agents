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
- Gateway maintenance triggers for iPhone session idle time and chat end.
- Later daily rollover design.

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
- User decision: Codex `PreCompact` owns token pressure; the gateway should not also schedule memory work from token usage.
- User decision: gateway idle consolidation starts with one hour of quiet after a gateway-observed iPhone message; daily rollover comes later.
- `../adi/.codex/config.toml` and `../angie/.codex/config.toml` are generated from `~/.agents/codex/config/repo-bootstrap.json`; do not hand-edit them.
- Dobby lifecycle `PreCompact` is now wired as a best-effort sidecar launch; `consolidate-thread` remains the reusable memory-writing primitive.
- Sidecar consolidation uses `DOBBY_LIFECYCLE_CONSOLIDATION_SIDECAR=1` to skip recursive PreCompact launches inside the consolidation App Server.

## Done When
- [x] Dobby workspace repos have a repo-local Codex auto-compaction threshold around 75% of the active model context window.
- [x] Direct Codex Dobby threads have a safe precompact memory-preservation path.
- [x] Gateway Dobby threads can use the same lifecycle primitive without racing live compaction.
- [x] Sidecar consolidation cannot recursively trigger another consolidation from its own compaction.
- [x] Validation covers control-plane rendering and the critical lifecycle path.

## Milestones
- [x] Milestone 1 - Repo-local Codex threshold is rendered for Dobby workspaces. Acceptance: `adi` and `angie` repo configs include `model_auto_compact_token_limit = 204000`, globals remain unchanged. Validate: `./codex/scripts/check-codex-control-plane.sh`.
- [x] Milestone 2 - PreCompact policy is wired for Dobby workspaces. Acceptance: direct Codex compaction in `adi` enqueues memory work without blocking compaction. Validate: local hook smoke plus App Server compact smoke.
- [x] Milestone 3 - Sidecar recursion guard is implemented. Acceptance: memory-consolidation sidecar compaction does not enqueue another memory-consolidation job. Validate: unit/smoke test with sidecar-labeled payload.
- [x] Milestone 4 - Gateway maintenance is aligned to lifecycle. Acceptance: gateway chat-end and idle paths trigger the shared maintenance primitive, while token pressure remains owned by Codex `PreCompact`. Validate: mobile-gateway tests, fast repo checks, and local gateway health smoke.

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
- Keep `consolidate-thread` sidecar-based. The consolidation App Server marks itself with `DOBBY_LIFECYCLE_CONSOLIDATION_SIDECAR=1`; PreCompact skips when that marker is present.

## Open Questions / Blockers
- None for the direct Codex path.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| done | Add and validate repo-local `model_auto_compact_token_limit` support and set `204000` for `adi`/`angie`. | parent | `/Users/dobby/.agents/codex/config/repo-bootstrap.json` |
| done | Wire and validate best-effort `PreCompact` sidecar launch for direct Codex threads. | parent | `/Users/dobby/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/pre-compact` |
| done | Design and implement the sidecar recursion guard after the basic path has settled. | parent | `/Users/dobby/.agents/skills-source/owned/dobby-lifecycle` |
| done | Align CodexClaw gateway policy: remove token-pressure consolidation, keep chat-end consolidation, and add one-hour iPhone idle consolidation. | parent | `/Users/dobby/GitHub/codexclaw/services/mobile-gateway` |

## Backlog / Remaining Work
- [x] Wire `PreCompact` hook assignment for `adi` and `angie` after local App Server behavior is verified.
- [x] Add a fast hook path that enqueues memory work without doing slow synthesis inline.
- [x] Add sidecar recursion guard and tests.
- [x] Align CodexClaw gateway maintenance with the shared lifecycle primitive.
- [x] Update lifecycle docs after behavior is proven.
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
- 2026-05-16: [DONE] Added the sidecar recursion guard. `consolidate-thread` marks its private App Server with `DOBBY_LIFECYCLE_CONSOLIDATION_SIDECAR=1`; PreCompact sees that marker, writes a skipped run record, and does not create another job. Validation added to Dobby lifecycle tests.
- 2026-05-16: [DONE] Aligned CodexClaw gateway maintenance. Removed gateway token-pressure consolidation and the context-ratio config; added one-hour iPhone idle consolidation for sessions updated during the current gateway process; kept `/v1/chat/end` consolidation and mapping cleanup. Validation passed: `npm run -w @codexclaw/mobile-gateway test`, `npm run check:fast`, launchd gateway refresh, and authenticated health smoke.
