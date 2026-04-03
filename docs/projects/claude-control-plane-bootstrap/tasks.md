# Claude Control Plane Bootstrap

## Goal
Bootstrap a Claude control plane in `~/.agents` that mirrors the current Codex control plane where it makes sense: global and project instructions, MCP, skills, agents, and permissive local defaults.

## Why / Impact
The repo already manages Codex as the primary control plane. Adding Claude as a managed secondary control plane reduces drift, keeps repo bootstrap reproducible across machines, and avoids ad-hoc per-repo Claude setup.

## Scope / Non-Goals
### In Scope
- Add a new `claude/` control-plane subtree in this repo.
- Define the global and project bootstrap model for Claude.
- Verify Anthropic’s current official settings and Agent SDK surfaces for prompt, permissions, sandbox, MCP, skills, and agents.
- Implement the first local-only bootstrap path with permissive defaults.
- Preserve `Codex` as the primary control plane and reuse shared registries only where sensible.

### Out of Scope
- Full `adi` `soul.md` parity in this first pass.
- VS Code cloud/remote agent prompt injection unless official docs show a stable config surface we can actually control here.
- Cross-machine secrets or OAuth credential bootstrapping.

## Context / Constraints
- Date started: 2026-04-02
- Current repo already has a mature Codex control plane under `codex/`.
- User wants Claude support added as a parallel secondary control plane, not merged into `codex/`.
- Generic repo compatibility should use `CLAUDE.md` files that import `@AGENTS.md`.
- The first pass should focus on the generic case and ignore the `adi` `soul.md` special case.
- Local-only workflow matters now more than cloud/remote execution.
- User wants broad permissive Claude defaults analogous to Codex `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`.

## Done When
- [x] A documented Claude bootstrap model exists in this repo with clear global/project layering.
- [x] A `claude/` control-plane subtree is added with canonical config and sync/check scripts for the first supported path.
- [x] Anthropic settings/schema/SDK assumptions used by the implementation are verified against official docs and recorded here.
- [x] The first local repo bootstrap output is rendered and validated for at least this repo.
- [x] Follow-up work needed for `adi` `soul.md` parity is captured separately instead of blocking the generic baseline.

## Milestones
- [x] Milestone 1 — Freeze the Claude bootstrap contract and verify Anthropic surfaces. Acceptance: tracker records the intended global/project model and doc-backed settings/SDK limits. Validate: official Anthropic docs cited in tracker/resources.
- [x] Milestone 2 — Add canonical `claude/` control-plane files and scripts. Acceptance: repo contains the first managed Claude config sources plus sync/check entrypoints. Validate: scripts dry-run cleanly.
- [x] Milestone 3 — Render local Claude bootstrap outputs for this repo and verify permissive defaults. Acceptance: generated outputs land where expected and match the agreed contract. Validate: generated files inspect cleanly and any repo validation path needed for touched files passes.
- [x] Milestone 4 — Document architecture and operations. Acceptance: architecture/reference docs explain the Claude control plane and how it differs from Codex. Validate: docs cite real paths/commands and align with implemented files.

## Execution Rules
- Keep the generic local-only Claude baseline first; do not let the `adi` special case derail the initial shape.
- Treat Anthropic official docs as authoritative for Claude behavior; record any docs/schema mismatch explicitly.
- Keep `Codex` as the primary control plane and add Claude as a sibling control plane.
- Reuse `skills/registry.json` when that improves shared capability routing, but do not force false parity where Claude’s model differs.
- Continue working until the first generic Claude control plane is implemented or a real blocker appears.

## Decisions
- `Codex` remains primary; Claude will be added as a sibling control plane under `claude/`.
- Generic project compatibility will use `CLAUDE.md` files that import `@AGENTS.md`.
- Nested `AGENTS.md` files should also receive sibling `CLAUDE.md` files that import `@AGENTS.md` for Claude parity.
- The first pass is local-only and intentionally ignores the `adi` `soul.md` special case.
- `skipDangerousModePermissionPrompt` is managed only at user/global Claude settings scope.
- The first pass manages instructions, MCP, settings, and skills; `.claude/agents/` is intentionally deferred.
- Global Claude MCP is merged into `~/.claude.json` without overwriting unrelated runtime keys.
- Special root repos with Codex `model_instructions_file` should render a real root `CLAUDE.md` that imports the resolved model-instructions file plus `@AGENTS.md`.
- `codex/config/repo-bootstrap.json` is the single shared repo registry for both Codex and Claude repo bootstrap.
- `mcp/config/presets.json` is the single shared MCP registry, with neutral `transport`-based preset definitions plus `global_presets`.
- `claude/config/bootstrap.json` is now only a Claude-specific defaults and per-repo override layer, not a second repo inventory.

## Open Questions / Blockers
- Anthropic’s published settings schema still lags at least one doc-backed key (`skipDangerousModePermissionPrompt`), so future schema patching remains an optional cleanup item.
- `adi` still needs a separate follow-up design for `soul.md` / host-level system prompt parity.
- Claude subagent materialization under `.claude/agents/` remains a follow-up if it proves useful in daily workflow.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| completed | Create project tracker, freeze contract, and scaffold the parent plan for the Claude control plane. | parent | `docs/projects/claude-control-plane-bootstrap/tasks.md` |
| completed | Verify Anthropic official docs for permissions, sandbox, settings schema, and MCP surfaces needed for local bootstrap. | external_researcher | `docs/projects/claude-control-plane-bootstrap/resources/anthropic-settings-research.md` |
| completed | Verify Anthropic official docs for skills, agents, `CLAUDE.md`, and Agent SDK prompt surfaces relevant to parity decisions. | external_researcher | `docs/projects/claude-control-plane-bootstrap/resources/anthropic-agent-surfaces.md` |
| completed | Inspect local repo patterns and scaffold the new `claude/` subtree in the same style as the existing `codex/` subtree. | parent | `claude/` |
| completed | Implement the first sync/check/bootstrap scripts for Claude global settings, global MCP, repo configs, and skills. | parent | `claude/scripts/` |
| completed | Apply and validate the first local-only bootstrap for `~/.agents`. | parent | `CLAUDE.md`, `.claude/settings.json`, `.mcp.json` |
| completed | Consolidate the Claude and Codex control planes onto one shared repo registry plus one shared MCP registry. | parent | `codex/config/repo-bootstrap.json`, `mcp/config/presets.json`, `claude/config/bootstrap.json` |

## Backlog / Remaining Work
- [ ] Add `.claude/agents/` materialization if Claude subagents become part of the control-plane baseline.
- [ ] Design the `adi` `soul.md` parity layer as a separate runtime/launcher concern.
- [ ] Decide whether to patch the published Claude settings schema locally for editor validation parity.
- [ ] Expand apply/validation beyond `~/.agents` once the generic baseline has enough usage feedback.
- [ ] Decide whether Claude needs any durable per-repo overrides beyond `claude/config/bootstrap.json`.
- [ ] Review and finalize `docs/projects/claude-control-plane-bootstrap/learnings/README.md`.
- [ ] Close out and archive the project when the generic baseline is complete.

## Validation / Test Plan
- Inspect Anthropic official docs for each behavior the implementation relies on.
- Run repo-local validation for touched scripts and generated files where a natural check exists.
- Dry-run any new sync/check scripts before claiming the bootstrap contract is stable.

## Progress Log
- 2026-04-02: [IN-PROGRESS] Created project tracker and froze the first-pass contract around a local-only generic Claude control plane.
- 2026-04-02: [DONE] Recorded official Anthropic settings/MCP and `CLAUDE.md`/skills/system prompt findings in project resource notes.
- 2026-04-02: [DONE] Added `claude/` canonical config plus sync/check/bootstrap scripts for global settings, global MCP, repo config rendering, and skills.
- 2026-04-02: [DONE] Applied the generic Claude bootstrap for `~/.agents`, including global `~/.claude` defaults and repo-local `CLAUDE.md`, `.claude/settings.json`, `.mcp.json`, and skill links.
- 2026-04-02: [DONE] Extended repo bootstrap to support nested `CLAUDE.md` import files for `@AGENTS.md` and special root `CLAUDE.md` rendering for repos with `model_instructions_file`.
- 2026-04-03: [IN-PROGRESS] Refactoring to a single shared repo registry (`codex/config/repo-bootstrap.json`) plus a shared neutral MCP registry (`mcp/config/presets.json`), with Claude reduced to a bootstrap overlay.
- 2026-04-03: [DONE] Finished the shared-registry refactor: Codex and Claude now both read repo assignment from `codex/config/repo-bootstrap.json`, both resolve MCP definitions from `mcp/config/presets.json`, Claude keeps only `claude/config/bootstrap.json` for defaults/overrides, the generated registry views were regenerated, and both control-plane validators passed.
