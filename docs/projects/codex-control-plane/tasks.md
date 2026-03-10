# Codex Control Plane Centralization

## Goal
Centralize canonical Codex control-plane assets in `~/.agents`, keep `~/.codex` as the applied runtime home, and thin `~/GitHub/scripts` down to bootstrap/apply entrypoints.

## Why / Impact
Codex setup is currently split across `~/.agents`, `~/.codex`, and `~/GitHub/scripts` in a way that makes ownership blurry. If this stays mixed, cross-machine sync, MCP policy, notify automation, and repo-local Codex behavior will keep drifting or require manual coordination.

## Scope / Non-Goals
### In Scope
- Define the target ownership model for Codex assets across `~/.agents`, `~/.codex`, `~/GitHub/scripts`, and repo-local `.codex/`.
- Create durable architecture and reference docs in `~/.agents`.
- Move or re-home canonical Codex-specific scripts/config/templates toward `~/.agents`.
- Update `~/GitHub/scripts` so it delegates to the `~/.agents` Codex control plane.
- Preserve a safe path for syncing the resulting setup across both machines.

### Out of Scope
- Migrating secrets, auth tokens, session history, or other volatile runtime state into git.
- Rewriting every repo-local `.codex/config.toml` in this project.
- Removing `~/.codex` runtime files that Codex actively manages.

## Context / Constraints
- Date started: 2026-03-10
- User intent: make `~/.agents` the personal Codex control plane synced across both machines.
- `~/GitHub/scripts/setup/codex/` currently owns portable Codex bootstrap assets and `setup/sync-codex-config.sh`.
- `~/.codex` currently mixes runtime state with a small amount of durable automation (`config.toml`, docs, and a few repo-specific files).
- Official Codex docs support user-level `~/.codex/config.toml` plus trusted project-scoped `.codex/config.toml` overrides, including `mcp_servers.<id>`.
- Keep live runtime state in `~/.codex` even if canonical managed inputs move elsewhere.
- Do not commit plaintext secrets or session artifacts.

## Done When
- [ ] `~/.agents` contains the canonical architecture and reference docs for the Codex control plane.
- [ ] Canonical Codex-specific managed assets have an explicit home under `~/.agents`.
- [ ] `~/GitHub/scripts` Codex setup delegates to `~/.agents` rather than owning Codex policy/details directly.
- [ ] The intended split between canonical source, applied runtime, and repo-local overrides is documented and validated.
- [ ] Remaining migration decisions and follow-ups are captured clearly for the next run.

## Milestones
- [x] Milestone 1 — Document the target control-plane design in `~/.agents`. Acceptance: architecture doc plus ownership reference exist and describe `.agents`, `~/.codex`, `~/GitHub/scripts`, and repo-local `.codex/`. Validate: review rendered Markdown and file paths.
- [x] Milestone 2 — Add or move the first canonical Codex control-plane assets into `~/.agents`. Acceptance: managed scripts/config sources live in `~/.agents` and docs point to them. Validate: inspect file tree and changed references.
- [x] Milestone 3 — Thin `~/GitHub/scripts` into bootstrap/apply entrypoints that call the `~/.agents` control plane. Acceptance: scripts still provide machine setup entrypoints, but Codex-specific source-of-truth is no longer duplicated there. Validate: dry-run relevant sync/apply commands where safe.
- [ ] Milestone 4 — Reconcile `~/.codex` as applied runtime home. Acceptance: runtime-vs-canonical boundary is explicit, and any remaining ambiguous files are recorded with a keep/move/generate decision. Validate: compare `~/.codex` contents against the ownership reference.

## Execution Rules
- Keep runtime-state handling conservative; do not delete live `~/.codex` state just because it should not be canonical.
- Prefer docs and non-destructive moves first, then script rewiring, then cleanup.
- Keep `~/GitHub/scripts` usable as the machine bootstrap entrypoint after each batch.
- Validate file references and dry-run flows before claiming the new ownership model works.
- Update this tracker before ending the run if scope or decisions change.

## Decisions
- `~/.agents` will become the canonical personal Codex control plane.
- `~/.codex` remains the applied runtime home, not the canonical source for durable Codex policy.
- Repo-local `.codex/config.toml` remains the right place for project-specific MCP/tool behavior when needed.
- `~/GitHub/scripts` should remain the bootstrap/apply shell, but not the long-term owner of Codex-specific policy and templates.

## Open Questions / Blockers
- Decide later whether `~/.codex` should remain a git-tracked repo or become runtime-only after canonical assets are moved out.
- Rotate the Cloudflare token that was previously stored in tracked `zshrc.shared`; it has been moved to a machine-local env file, but the old token value should still be treated as exposed.

## Tasks
- [x] Create `docs/architecture/codex-control-plane.md`.
- [x] Create `docs/references/codex-control-plane-ownership.md`.
- [x] Audit current Codex-related files in `~/.agents`, `~/.codex`, and `~/GitHub/scripts` against the target ownership model.
- [x] Create the canonical Codex control-plane folder structure in `~/.agents`.
- [x] Move or copy the first Codex-specific managed assets into the new canonical location.
- [x] Update `~/GitHub/scripts` Codex setup scripts to delegate to `~/.agents`.
- [x] Update relevant `AGENTS.md` and docs references if ownership boundaries change materially.
- [x] Run safe validation for the changed apply/sync entrypoints.
- [ ] Record final keep / move / generate decisions for `~/.codex`.
- [ ] Finish the shell-side split and validate shared zshrc + Ghostty bootstrap through the new `~/.agents` Codex fragment.

## Validation / Test Plan
- Review new docs for consistency with the current file layout and intended ownership split.
- Use dry-run or non-destructive invocations of Codex setup/apply scripts where available.
- Re-read touched `AGENTS.md` and script paths to ensure the new control-plane boundary is explicit.
- Run `bash -n` on moved shell scripts and `python3 -m py_compile` on moved Python scripts.
- Do not mutate or migrate secrets, auth files, histories, sessions, or live runtime databases.

## Progress Log
- 2026-03-10: [IN-PROGRESS] Created project tracker and gathered the initial ownership audit across `~/.agents`, `~/.codex`, and `~/GitHub/scripts`.
- 2026-03-10: [IN-PROGRESS] Added the first canonical Codex control-plane structure under `~/.agents/codex`, moved managed config templates there, and switched `~/GitHub/scripts/setup/sync-codex-config.sh` to a wrapper.
- 2026-03-10: [IN-PROGRESS] Moved the canonical notify script source into `~/.agents/codex/scripts` and pointed live Codex notify config at the new path.
- 2026-03-10: [IN-PROGRESS] Validated the new control plane with `bash -n`, `python3 -m py_compile`, `./setup/sync-codex-config.sh --global-only`, and `./setup/sync-codex-config.sh --apply --xcode-only`.
- 2026-03-10: [IN-PROGRESS] Split Codex/Ghostty shell behavior out of `setup/codex/zshrc.shared`, moved the Codex fragment to `~/.agents/codex/shell/codex-shell.zsh`, and moved the Ghostty startup helpers into `~/.agents/codex/scripts`.

## Next 3 Actions
1. Validate shared zshrc and Ghostty startup through the new `~/.agents` shell fragment and script wrappers.
2. Reconcile `.codex` repo-specific files against the new control-plane ownership model.
3. Decide whether `~/.codex` should remain a git-tracked repo or be reduced to runtime-only state plus generated config.
