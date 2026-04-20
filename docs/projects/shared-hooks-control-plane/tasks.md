# Shared Hooks Control Plane

## Goal
Create a shared, validated hook control plane that renders global Codex and Claude lifecycle hooks from one canonical registry.

## Why / Impact
Hooks will become a common agent-native feedback loop across repositories. A shared registry and renderer keeps Codex and Claude behavior aligned while preserving each runtime's native config shape.

## Scope / Non-Goals
### In Scope
- Global `SessionStart` and `Stop` hooks for Codex and Claude.
- A shared no-op `SessionStart` hook runner.
- Shared `Stop` hook git finalization that stages, commits, reports repo-owned pre-commit failures to the current agent, rebases, and pushes.
- Shared local Git `pre-commit` hook for managed repos.
- Codex Plan Mode high reasoning in canonical bootstrap config.
- Validation and docs for the new rendered surfaces.

### Out of Scope
- Repo-local hook rendering.
- Session-start context injection.
- Claude-only `SessionEnd`.

## Context / Constraints
- Date started: 2026-04-20
- Codex hooks require `[features].codex_hooks = true`.
- Codex global hooks render to `~/.codex/hooks.json`.
- Claude global hooks render into `~/.claude/settings.json`.
- `Stop` is turn-scoped, so it must stay silent and fast when the repo is clean.
- Hook stdout is runtime protocol output, so hook runners print nothing on success.

## Done When
- [x] Codex and Claude global lifecycle hooks render from `hooks/registry.json`.
- [x] The shared hook runners exit successfully and emit no stdout on success.
- [x] `Stop` hook replaces the legacy Codex post-turn path and blocks with useful failure context when repo checks fail.
- [x] Codex config renders `model = "gpt-5.4"` and `plan_mode_reasoning_effort = "high"`.
- [x] Control-plane checks and tests pass after notify removal.
- [x] Managed repos use shared local Git `core.hooksPath`.

## Milestones
- [x] Milestone 1 — V1 shared hooks. Acceptance: Codex and Claude render global `SessionStart` and `Stop` from one registry. Validate: `./scripts/test-control-plane.sh`.
- [x] Milestone 2 — Bootstrap/check integration. Acceptance: machine bootstrap applies hooks and checks detect drift. Validate: `./scripts/check-agent-control-planes.sh`.
- [x] Milestone 3 — Stop hook git conveyor. Acceptance: legacy post-turn scripts/config are gone, `Stop` commits/pushes, and failed repo checks block the current agent with actionable output. Validate: `./scripts/test-control-plane.sh` and `./scripts/check-agent-control-planes.sh`.
- [x] Milestone 4 — Managed repo local pre-commit consolidation. Acceptance: managed repos point local `core.hooksPath` at `hooks/git`, and the shared hook delegates to repo-owned pre-commit/Husky checks. Validate: `./scripts/sync-managed-git-hooks.sh --check` and `./scripts/check-agent-control-planes.sh`.

## Execution Rules
- Keep `SessionStart` behavior no-op and successful unless the hook command itself is invoked with invalid CLI arguments.
- Keep stdout empty for hook success; only write runtime hook protocol JSON when `Stop` needs to continue/block.
- Keep runtime config native to each client; the shared layer owns intent, not runtime schema replacement.
- Update this tracker when scope or hook behavior changes materially.

## Decisions
- Use a neutral `hooks/registry.json` instead of `owned` / `external` source buckets for v1.
- Render native Codex `hooks.json` and merge native Claude `settings.json` hook entries.
- Keep both hooks global in v1.
- Add Codex `plan_mode_reasoning_effort = "high"`; there is no separate supported `plan_mode_model` key.
- Replace the legacy Codex post-turn path with the shared `Stop` hook instead of spawning a second agent process.
- Drop audible completion notification from the post-turn path.
- Keep local Git hook config machine-local through `core.hooksPath`; do not change GitHub Actions workflows for this.

## Open Questions / Blockers
- None.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| done | Consolidate managed repo local Git pre-commit entrypoint | parent |  |

## Backlog / Remaining Work
- [ ] Add optional repo-local `SessionStart` context injection.
- [ ] Decide whether Claude-only `SessionEnd` belongs in a runtime-specific extension layer.
- [ ] Archive or refresh this tracker after the v1 validation result is recorded.

## Validation / Test Plan
- `./codex/scripts/check-codex-control-plane.sh`
- `./claude/scripts/check-claude-control-plane.sh`
- `./scripts/check-agent-control-planes.sh`
- `./scripts/test-control-plane.sh`

## Progress Log
- 2026-04-20: [IN-PROGRESS] Created project tracker and started v1 implementation.
- 2026-04-20: [DONE] Implemented v1 global `SessionStart` and `Stop` hooks for Codex and Claude; validation passed with `./scripts/check-agent-control-planes.sh`.
- 2026-04-20: [DONE] Removed legacy Codex post-turn scripts/config and moved the git conveyor into the shared `Stop` hook; validation passed with `./scripts/test-control-plane.sh` and `./scripts/check-agent-control-planes.sh`.
- 2026-04-20: [DONE] Consolidated managed repo local pre-commit entrypoints through shared `core.hooksPath`; validation passed with `./scripts/sync-managed-git-hooks.sh --check` and `./scripts/check-agent-control-planes.sh`.
