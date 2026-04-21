# Shared Hooks Control Plane

## Goal
Create a shared, validated hook control plane that renders Codex, Claude, and managed repo-local GitHub Copilot hooks from one canonical registry.

## Why / Impact
Hooks will become a common agent-native feedback loop across repositories. A shared registry and renderer keeps Codex, Claude, and GitHub Copilot behavior aligned while preserving each runtime's native config shape.

## Scope / Non-Goals
### In Scope
- Global `SessionStart`, `UserPromptSubmit`, and `Stop` hooks for Codex and Claude.
- Managed repo-local GitHub Copilot hook config rendered to `.github/hooks/agent-control-plane.json`.
- Claude and GitHub Copilot global/logical `SessionEnd` hook.
- A shared `SessionStart` hook runner that stays silent unless the current repo defines `scripts/hooks/session-start.sh`.
- A shared `UserPromptSubmit` hook runner that stays silent unless the current repo defines `scripts/hooks/user-prompt-submit.sh`.
- A shared `SessionEnd` hook runner that stays silent unless the current repo defines `scripts/hooks/session-end.sh`.
- Shared `Stop` hook git finalization that stages, commits, reports repo-owned fast-check failures to the current agent, rebases, and pushes.
- Optional repo-owned `SessionStart` startup context through `scripts/hooks/session-start.sh`.
- Shared local Git commit-time hook for managed repos.
- Codex Plan Mode high reasoning in canonical bootstrap config.
- Validation and docs for the new rendered surfaces.

### Out of Scope
- GitHub Copilot tool-use hooks such as `preToolUse` or `postToolUse`.
- Copilot cloud-specific behavior beyond guarded no-op commands when `~/.agents` is absent.

## Context / Constraints
- Date started: 2026-04-20
- Codex hooks require `[features].codex_hooks = true`.
- Codex global hooks render to `~/.codex/hooks.json`.
- Claude global hooks render into `~/.claude/settings.json`.
- GitHub Copilot hook files render into managed repos under `.github/hooks/agent-control-plane.json`.
- `Stop` is turn-scoped, so it must stay silent and fast when the repo is clean.
- Hook stdout is runtime protocol output, so hook runners print nothing on success.

## Done When
- [x] Codex and Claude global lifecycle hooks render from `hooks/registry.json`.
- [x] The shared hook runners exit successfully and emit no stdout on success.
- [x] `Stop` hook replaces the legacy Codex post-turn path and blocks with useful failure context when repo checks fail.
- [x] Codex config renders `model = "gpt-5.4"` and `plan_mode_reasoning_effort = "high"`.
- [x] Control-plane checks and tests pass after notify removal.
- [x] Managed repos use shared local Git `core.hooksPath`.
- [x] Repo-owned `scripts/hooks/session-start.sh` runs from the shared `SessionStart` dispatcher when present.
- [x] Repo-owned `scripts/hooks/user-prompt-submit.sh` runs from the shared `UserPromptSubmit` dispatcher when present.
- [x] Repo-owned `scripts/hooks/session-end.sh` runs from the shared Claude and GitHub Copilot `SessionEnd` dispatcher when present.
- [x] Managed repos get repo-local GitHub Copilot hook config rendered from `hooks/registry.json`.

## Milestones
- [x] Milestone 1 — V1 shared hooks. Acceptance: Codex and Claude render global `SessionStart` and `Stop` from one registry. Validate: `./scripts/test-control-plane.sh`.
- [x] Milestone 2 — Bootstrap/check integration. Acceptance: machine bootstrap applies hooks and checks detect drift. Validate: `./scripts/check-agent-control-planes.sh`.
- [x] Milestone 3 — Stop hook git conveyor. Acceptance: legacy post-turn scripts/config are gone, `Stop` commits/pushes, and failed repo checks block the current agent with actionable output. Validate: `./scripts/test-control-plane.sh` and `./scripts/check-agent-control-planes.sh`.
- [x] Milestone 4 — Managed repo local commit-time check consolidation. Acceptance: managed repos point local `core.hooksPath` at `hooks/git`, and the shared hook delegates to repo-owned `scripts/check-fast.sh` when present. Validate: `./scripts/sync-managed-git-hooks.sh --check` and `./scripts/check-agent-control-planes.sh`.
- [x] Milestone 5 — GitHub Copilot hook rendering. Acceptance: managed repos render `.github/hooks/agent-control-plane.json` from the shared hook registry. Validate: `./scripts/sync-copilot-hooks.sh --check` and `./scripts/check-agent-control-planes.sh`.

## Execution Rules
- Keep `SessionStart` behavior no-op and successful when no repo script exists.
- Keep `SessionStart` stdout empty when no repo script exists; when a repo script exists, stdout is intentional startup context.
- Keep `UserPromptSubmit` behavior no-op and successful when no repo script exists; when a repo script exists, stdout is intentional prompt context.
- Keep `SessionEnd` off Codex until Codex exposes a documented equivalent.
- Keep Copilot commands guarded so GitHub cloud agent no-ops when this local `~/.agents` control plane is not installed in the cloud runner.
- Only write runtime hook protocol JSON when `Stop` needs to continue/block.
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
- Use `scripts/hooks/session-start.sh` as the repo-owned startup context convention. The shared dispatcher owns discovery and forwarding only.
- Use `scripts/hooks/user-prompt-submit.sh` as the repo-owned prompt context convention.
- Use `scripts/hooks/session-end.sh` as the repo-owned session cleanup convention for runtimes that expose `SessionEnd`. The shared dispatcher logs stdout instead of injecting context because the session is ending.
- Render GitHub Copilot's logical turn-stop event as `agentStop`, mapped from the shared `Stop` registry event.

## Open Questions / Blockers
- None.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| done | Consolidate managed repo local Git commit-time check entrypoint | parent |  |

## Backlog / Remaining Work
- [x] Add optional repo-local `SessionStart` context injection.
- [x] Add optional repo-local `UserPromptSubmit` context injection.
- [x] Add optional repo-local Claude and GitHub Copilot `SessionEnd` cleanup.
- [x] Render repo-local GitHub Copilot hook files from the shared registry.
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
- 2026-04-20: [DONE] Consolidated managed repo local commit-time entrypoints through shared `core.hooksPath`; validation passed with `./scripts/sync-managed-git-hooks.sh --check` and `./scripts/check-agent-control-planes.sh`.
- 2026-04-20: [DONE] Added repo-owned `SessionStart` dispatch through `scripts/hooks/session-start.sh`; Adi now delegates startup context to `dobby-memory boot`.
- 2026-04-21: [DONE] Added shared `UserPromptSubmit` dispatch for Codex and Claude plus `SessionEnd` dispatch; focused hook tests passed with `python3 -m unittest tests.control_plane.test_hooks_control_plane`.
- 2026-04-21: [DONE] Added GitHub Copilot hook rendering from `hooks/registry.json` into managed repo `.github/hooks/agent-control-plane.json`; focused hook and orchestration tests passed with `python3 -m unittest tests.control_plane.test_hooks_control_plane tests.control_plane.test_orchestration`.
