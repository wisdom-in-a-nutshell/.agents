# .agents repo

Personal agent, Codex, and Claude control plane.

## Purpose

- Keep global skill sources and runtime links reproducible across MacBook + MacMini.
- Keep canonical personal Codex control-plane assets reproducible across MacBook + MacMini.
- Track one canonical skill registry in git.
- Keep repo-local skills in their repos unless explicitly promoted.

## Source of Truth

- `skills/registry.json` is the canonical skill registry.
- `plugins/registry.json` is the canonical plugin registry.
- `mcp/config/presets.json` is the canonical shared MCP registry.
- `agents/registry.json` is the canonical shared agent registry for Codex agents and Claude subagents.
- `hooks/registry.json` is the canonical shared lifecycle hook registry for Codex and Claude.
- `codex/` holds canonical personal Codex control-plane inputs.
- `codex/config/global.agents.md` is the single canonical machine-wide guidance source for both `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md`.
- `codex/config/repo-bootstrap.json` is the canonical shared repo registry for managed repo-local behavior.
  - Per repo it can define:
    - `mcp_presets`
    - `model`
    - `model_reasoning_effort`
    - `plan_mode_reasoning_effort`
    - `model_verbosity`
    - `personality`
    - `model_instructions_file`
    - `developer_instructions`
    - `project_root_markers`
    - `features`
    - `service_tier`
- Managed canonical skill content lives in:
  - `skills-source/external/<skill>/`
  - `skills-source/owned/<skill>/`
- Managed canonical plugin content lives in:
  - `plugins-source/external/<plugin>/`
  - `plugins-source/owned/<plugin>/`
- Global runtime skills live in `skills/<skill>` as symlinks.
- Plugin-derived skill assignments render into `skills/registry.json` under `managed_plugin_skills`.
- Plugin-derived shared MCP presets render into `mcp/config/presets.json` under `plugin_presets` and `plugin_global_presets`.
- Plugin-derived repo MCP assignments render into `codex/config/repo-bootstrap.json` under `plugin_mcp_presets`.
- Generated views for Obsidian live in:
  - `docs/references/registry/skills.base`
  - `docs/references/registry/skills-items/`
  - `docs/references/registry/repo-bootstrap.base`
  - `docs/references/registry/repo-bootstrap-items/`
  - `docs/references/registry/agent-registry.base`
  - `docs/references/registry/agent-registry-items/`
  - `docs/references/registry/mcp-registry.base`
  - `docs/references/registry/mcp-registry-items/`
- Shared lifecycle hook scripts live in:
  - `hooks/scripts/`
- Shared local Git hook scripts live in:
  - `hooks/git/`

## Key Entry Points

- Apply all shared agent control planes: `./scripts/bootstrap-machine-agent-control-planes.sh --apply`
- Reconcile after git sync: `./scripts/auto-apply-agent-control-planes.sh --apply`
- Validate shared skills, plugins, Codex, Claude, and regression tests: `./scripts/check-agent-control-planes.sh`
- Run hermetic regression tests only: `./scripts/test-control-plane.sh`
- Bootstrap external skills/plugins through the agent-facing clients:
  - `./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo>`
  - `./scripts/bootstrap-plugin.sh <plugin-name-or-id> --repo <repo>`

Detailed operations live in:

- `docs/references/agent-control-plane-operations.md`
- `docs/references/codex-control-plane-operations.md`
- `docs/references/claude-control-plane-operations.md`
- `docs/references/cli-interface-contract.md`

## Rendered Surfaces

- Treat paths listed in `docs/references/rendered-surfaces.md` as linked, rendered, or generated outputs.
- Do not hand-edit rendered outputs; update the canonical source and rerun the documented renderer/check.

## Rules

- Runtime distribution is link-first for skills; plugin source stays canonical under `plugins-source/` and feeds extracted skills plus MCP.
- Treat global skills as a minimal default kit; prefer repo scope or repo-local unless a skill is broadly useful across unrelated repos.
- When a user provides a `skills.sh` URL or upstream skill reference and wants it installed into a repo, prefer `./scripts/bootstrap-skill.sh` over manual registry edits.
- Do not edit managed skills through repo symlink destinations; edit canonical source paths.
- Do not edit plugin-derived skills, MCP, or repo runtime files as source; edit canonical plugin source paths and `plugins/registry.json`.
- Do not make `claude/config/global.claude.md` diverge from `codex/config/global.agents.md`; it must stay a symlink alias to the shared global guidance source.
- Managed plugins can mirror upstream source under `plugins-source/external/` when the control plane extracts bundled skills and `.mcp.json` into the normal skills and MCP flows.
- Keep repo-local skills listed in `skills/registry.json` under `unmanaged_repo_local_skills`.
- Keep `unmanaged_repo_local_skills` honest: if the target repo exists locally, the repo must contain `.agents/skills/<skill>/SKILL.md` or skill sync should fail until the stale registry entry is removed.
- Keep repo-local plugins listed in `plugins/registry.json` under `unmanaged_repo_local_plugins`.
- Do not add additional manifest files for skill mapping; update `skills/registry.json`.
- Do not add additional manifest files for plugin mapping; update `plugins/registry.json`.
- New or promoted agent-facing CLI clients must follow `docs/references/cli-interface-contract.md`.
- Do not hand-edit rendered runtime hook files. Update `hooks/registry.json` or `hooks/scripts/*`, then rerun the shared bootstrap/check.
- Managed repos use local Git `core.hooksPath` pointing at `hooks/git/`; the shared commit-time hook delegates to repo-owned `scripts/check-fast.sh` when present.
- Use `scripts/check-fast.sh` as the fast, deterministic, repo-owned validation entrypoint. Keep slower validation in a separate script such as `scripts/check-full.sh`.
- If `skills/registry.json` changes, run sync/check in the same change.
- If `plugins/registry.json` changes, run plugin sync/check in the same change.
- Do not hand-edit generated repo-local `.codex/config.toml` files in managed repos; update `codex/config/repo-bootstrap.json` and re-run the sync scripts.
- Do not hand-edit generated repo-local `.codex/agents/*.toml` files in managed repos; update `codex/config/repo-bootstrap.json` or `codex/config/agents/*.toml` and re-run the sync scripts.
- When changing shared bootstrap inputs such as `mcp/config/presets.json`, `codex/config/repo-bootstrap.json`, or repo MCP assignment, prefer `./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo <repo>` so Codex and Claude repo-local state are both re-rendered together. Use component-only Codex or Claude scripts only for intentional single-surface troubleshooting.
- If `mcp/config/presets.json` changes, run both Codex and Claude control-plane validation in the same change.
- If `agents/registry.json` changes, run both Codex and Claude control-plane validation plus `./scripts/test-control-plane.sh` in the same change.
- If `hooks/registry.json`, `hooks/scripts/*`, `hooks/git/*`, or `scripts/sync-managed-git-hooks.sh` changes, run shared bootstrap/check plus `./scripts/test-control-plane.sh` in the same change.
- If `codex/config/agents/*.toml`, `codex/config/global.config.toml`, `codex/config/xcode.config.toml`, or `codex/config/repo-bootstrap.json` changes, run the Codex control-plane validation script in the same change.
