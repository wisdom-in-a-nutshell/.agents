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
- Generic repo compatibility should use `CLAUDE.md -> AGENTS.md`.
- The first pass should focus on the generic case and ignore the `adi` `soul.md` special case.
- Local-only workflow matters now more than cloud/remote execution.
- User wants broad permissive Claude defaults analogous to Codex `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`.

## Done When
- [ ] A documented Claude bootstrap model exists in this repo with clear global/project layering.
- [ ] A `claude/` control-plane subtree is added with canonical config and sync/check scripts for the first supported path.
- [ ] Anthropic settings/schema/SDK assumptions used by the implementation are verified against official docs and recorded here.
- [ ] The first local repo bootstrap output is rendered and validated for at least this repo.
- [ ] Follow-up work needed for `adi` `soul.md` parity is captured separately instead of blocking the generic baseline.

## Milestones
- [ ] Milestone 1 — Freeze the Claude bootstrap contract and verify Anthropic surfaces. Acceptance: tracker records the intended global/project model and doc-backed settings/SDK limits. Validate: official Anthropic docs cited in tracker/resources.
- [ ] Milestone 2 — Add canonical `claude/` control-plane files and scripts. Acceptance: repo contains the first managed Claude config sources plus sync/check entrypoints. Validate: scripts dry-run cleanly.
- [ ] Milestone 3 — Render local Claude bootstrap outputs for this repo and verify permissive defaults. Acceptance: generated outputs land where expected and match the agreed contract. Validate: generated files inspect cleanly and any repo validation path needed for touched files passes.
- [ ] Milestone 4 — Document architecture and operations. Acceptance: architecture/reference docs explain the Claude control plane and how it differs from Codex. Validate: docs cite real paths/commands and align with implemented files.

## Execution Rules
- Keep the generic local-only Claude baseline first; do not let the `adi` special case derail the initial shape.
- Treat Anthropic official docs as authoritative for Claude behavior; record any docs/schema mismatch explicitly.
- Keep `Codex` as the primary control plane and add Claude as a sibling control plane.
- Reuse `skills/registry.json` when that improves shared capability routing, but do not force false parity where Claude’s model differs.
- Continue working until the first generic Claude control plane is implemented or a real blocker appears.

## Decisions
- `Codex` remains primary; Claude will be added as a sibling control plane under `claude/`.
- Generic project compatibility will use `CLAUDE.md -> AGENTS.md`.
- The first pass is local-only and intentionally ignores the `adi` `soul.md` special case.

## Open Questions / Blockers
- Does Anthropic’s published settings schema fully cover the doc-backed keys needed for permissive defaults, or do we need a patched local schema?
- Which parts of the current shared skills registry should be materialized into Claude global/project skills in the first pass versus deferred?
- How should Claude global MCP be represented canonically in this repo versus machine-local runtime state?

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| in_progress | Create project tracker, freeze contract, and scaffold the parent plan for the Claude control plane. | parent |  |
| delegated | Verify Anthropic official docs for permissions, sandbox, settings schema, and MCP surfaces needed for local bootstrap. | external_researcher | `docs/projects/claude-control-plane-bootstrap/resources/anthropic-settings-research.md` |
| delegated | Verify Anthropic official docs for skills, agents, `CLAUDE.md`, and Agent SDK prompt surfaces relevant to parity decisions. | external_researcher | `docs/projects/claude-control-plane-bootstrap/resources/anthropic-agent-surfaces.md` |
| todo | Inspect local repo patterns and scaffold the new `claude/` subtree in the same style as the existing `codex/` subtree. | parent |  |

## Backlog / Remaining Work
- [ ] Decide the canonical file layout for `claude/config/`, `claude/scripts/`, and any generated views.
- [ ] Add a managed global Claude settings source with permissive defaults.
- [ ] Add a managed global Claude instruction source for `~/.claude/CLAUDE.md`.
- [ ] Decide how global Claude skills should be materialized from `skills/registry.json`.
- [ ] Decide how project Claude MCP should be rendered from a repo bootstrap registry.
- [ ] Add sync/check scripts for Claude.
- [ ] Dry-run and apply the first local bootstrap for this repo.
- [ ] Update architecture docs for the Claude sibling control plane.
- [ ] Update reference docs with exact commands/paths for Claude operations.
- [ ] Review and finalize `docs/projects/claude-control-plane-bootstrap/learnings/README.md`.
- [ ] Close out and archive the project when the generic baseline is complete.

## Validation / Test Plan
- Inspect Anthropic official docs for each behavior the implementation relies on.
- Run repo-local validation for touched scripts and generated files where a natural check exists.
- Dry-run any new sync/check scripts before claiming the bootstrap contract is stable.

## Progress Log
- 2026-04-02: [IN-PROGRESS] Created project tracker and froze the first-pass contract around a local-only generic Claude control plane.
