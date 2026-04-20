# Shared Hooks Control Plane

## Goal
Create a shared, validated hook control plane that renders global Codex and Claude lifecycle hooks from one canonical registry.

## Why / Impact
Hooks will become a common agent-native feedback loop across repositories. A shared registry and renderer keeps Codex and Claude behavior aligned while preserving each runtime's native config shape.

## Scope / Non-Goals
### In Scope
- Global `SessionStart` and `Stop` hooks for Codex and Claude.
- A shared no-op lifecycle hook runner.
- Codex Plan Mode high reasoning in canonical bootstrap config.
- Validation and docs for the new rendered surfaces.

### Out of Scope
- Repo-local hook rendering.
- Session-start context injection.
- Git commit/finalization behavior in `Stop`.
- Moving `notify.py` into hooks.
- Claude-only `SessionEnd`.

## Context / Constraints
- Date started: 2026-04-20
- Codex hooks require `[features].codex_hooks = true`.
- Codex global hooks render to `~/.codex/hooks.json`.
- Claude global hooks render into `~/.claude/settings.json`.
- `Stop` is turn-scoped, so v1 must remain silent and cheap.
- Hook stdout is runtime protocol output, so the v1 runner prints nothing on success.

## Done When
- [x] Codex and Claude global lifecycle hooks render from `hooks/registry.json`.
- [x] The shared lifecycle runner exits successfully and emits no stdout for `SessionStart` and `Stop`.
- [x] Codex config renders `model = "gpt-5.4"` and `plan_mode_reasoning_effort = "high"`.
- [x] Control-plane checks and tests pass.

## Milestones
- [x] Milestone 1 — V1 no-op lifecycle hooks. Acceptance: Codex and Claude render global `SessionStart` and `Stop` from one registry. Validate: `./scripts/test-control-plane.sh`.
- [x] Milestone 2 — Bootstrap/check integration. Acceptance: machine bootstrap applies hooks and checks detect drift. Validate: `./scripts/check-agent-control-planes.sh`.

## Execution Rules
- Keep v1 behavior no-op and successful unless the hook command itself is invoked with invalid CLI arguments.
- Keep stdout empty for the lifecycle runner unless a later milestone intentionally adds runtime-specific hook protocol output.
- Keep runtime config native to each client; the shared layer owns intent, not runtime schema replacement.
- Update this tracker when scope or hook behavior changes materially.

## Decisions
- Use a neutral `hooks/registry.json` instead of `owned` / `external` source buckets for v1.
- Render native Codex `hooks.json` and merge native Claude `settings.json` hook entries.
- Keep both hooks global in v1.
- Add Codex `plan_mode_reasoning_effort = "high"`; there is no separate supported `plan_mode_model` key.

## Open Questions / Blockers
- None.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| done | Implement v1 shared no-op lifecycle hooks and validation | parent |  |

## Backlog / Remaining Work
- [ ] Add optional repo-local `SessionStart` context injection.
- [ ] Add `Stop` git status fast path.
- [ ] Add `Stop` continuation behavior for failed finalization.
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
