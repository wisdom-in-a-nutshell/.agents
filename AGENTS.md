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
- `codex/` holds canonical personal Codex control-plane inputs.
- `codex/config/repo-bootstrap.json` is the canonical shared repo registry for managed repo-local behavior.
  - Per repo it can define:
    - `mcp_presets`
    - `model`
    - `model_reasoning_effort`
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

## Operations

- Dry-run machine-facing agent bootstrap batch: `./scripts/bootstrap-machine-agent-control-planes.sh`
- Apply machine-facing agent bootstrap batch: `./scripts/bootstrap-machine-agent-control-planes.sh --apply`
  - Syncs managed skill links, plugin-derived skills/MCP state, plus the Codex and Claude control-plane runtimes from one stable `~/.agents` entrypoint.
- Dry-run post-sync agent control-plane reconcile: `./scripts/auto-apply-agent-control-planes.sh --dry-run`
- Apply post-sync agent control-plane reconcile: `./scripts/auto-apply-agent-control-planes.sh --apply`
  - Detects runtime-relevant changes in `skills/`, `skills-source/`, `mcp/`, `codex/`, and `claude/`, then runs the necessary shared apply steps.
- Validate shared skills + Codex + Claude rendered state: `./scripts/check-agent-control-planes.sh`
- Run hermetic control-plane regression tests: `./scripts/test-control-plane.sh`
- Dry-run skill bootstrap: `./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo>`
- Apply skill bootstrap: `./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo> --apply`
  - Bootstraps a managed external skill by updating `skills/registry.json`, importing upstream source, syncing links, and regenerating derived registry artifacts.
- Dry-run sync: `./scripts/sync-skills-registry.sh`
- Apply sync: `./scripts/sync-skills-registry.sh --apply`
  - Sync applies desired managed links and prunes obsolete managed global runtime links.
- Validate generated registry artifacts: `./scripts/check-skills-registry.sh`
- Dry-run external upstream refresh: `./scripts/refresh-external-skills.sh`
- Apply external upstream refresh: `./scripts/refresh-external-skills.sh --apply`
  - Refresh preserves local `agents/openai.yaml` inside external skill folders.
- Dry-run plugin sync: `./scripts/sync-plugins-registry.sh`
- Apply plugin sync: `./scripts/sync-plugins-registry.sh --apply`
  - Sync validates `plugins/registry.json`, regenerates the Obsidian registry views, and refreshes plugin-derived skills plus MCP state.
- Validate generated plugin registry artifacts: `./scripts/check-plugins-registry.sh`
- Dry-run external plugin refresh: `./scripts/refresh-external-plugins.sh`
- Apply external plugin refresh: `./scripts/refresh-external-plugins.sh --apply`
  - Refresh preserves local `agents/openai.yaml` inside external plugin source folders.
- Dry-run plugin bootstrap: `./scripts/bootstrap-plugin.sh <plugin-name-or-id>`
- Apply plugin bootstrap: `./scripts/bootstrap-plugin.sh <plugin-name-or-id> --apply`
  - Bootstraps a managed plugin source by updating `plugins/registry.json`, refreshing upstream source, regenerating plugin-derived registry artifacts, and applying shared skills plus Codex and Claude bootstraps.
- Dry-run Codex config apply: `./codex/scripts/sync-config.sh`
- Apply Codex config: `./codex/scripts/sync-config.sh --apply`
- Dry-run Codex global AGENTS apply: `./codex/scripts/sync-global-agents-md.sh`
- Apply Codex global AGENTS apply: `./codex/scripts/sync-global-agents-md.sh --apply`
- Dry-run Codex trust sync: `./codex/scripts/sync-trusted-projects.sh`
- Apply Codex trust sync: `./codex/scripts/sync-trusted-projects.sh --apply`
- Rebuild Codex repo bootstrap Base artifacts: `./codex/scripts/sync-repo-bootstrap-registry.sh`
- Apply managed repo-local Codex configs: `./codex/scripts/sync-repo-codex-configs.sh --apply`
- Dry-run Claude bootstrap batch: `./claude/scripts/bootstrap-machine-claude.sh`
- Apply Claude bootstrap batch: `./claude/scripts/bootstrap-machine-claude.sh --apply`
- Claude bootstrap now validates rendered state at the end of the batch.
- Validate Claude control-plane inputs + rendered runtimes: `./claude/scripts/check-claude-control-plane.sh`
- Dry-run Codex bootstrap batch: `./codex/scripts/bootstrap-machine-codex.sh`
- Apply Codex bootstrap batch: `./codex/scripts/bootstrap-machine-codex.sh --apply`
  - This applies the Codex control-plane outputs only; the shared shell links still live in `~/GitHub/scripts`.
- Link shared zshrc: `~/GitHub/scripts/setup/codex/link-shared-zshrc.sh --apply`
- Link shared zprofile: `~/GitHub/scripts/setup/codex/link-shared-zprofile.sh --apply`
- Validate Codex control-plane inputs + rendered runtimes: `./codex/scripts/check-codex-control-plane.sh`

## Automation Cadence

- Scheduler entrypoint lives in `~/GitHub/scripts/sync/git-auto-sync.sh` (launchd every 15 minutes).
- External upstream refresh runs through that job with a once-per-day gate:
  - `~/.agents/scripts/refresh-external-skills.sh --apply`
- External plugin upstream refresh now runs through the shared reconcile wrapper with a once-per-day gate:
  - `~/.agents/scripts/refresh-external-plugins.sh --apply`
- Shared agent control-plane reconcile runs every auto-sync cycle:
  - `~/.agents/scripts/auto-apply-agent-control-planes.sh --apply`

## Rules

- Runtime distribution is link-first for skills; plugin source stays canonical under `plugins-source/` and feeds extracted skills plus MCP.
- Treat global skills as a minimal default kit; prefer repo scope or repo-local unless a skill is broadly useful across unrelated repos.
- When a user provides a `skills.sh` URL or upstream skill reference and wants it installed into a repo, prefer `./scripts/bootstrap-skill.sh` over manual registry edits.
- Do not edit managed skills through repo symlink destinations; edit canonical source paths.
- Do not edit plugin-derived skills, MCP, or repo runtime files as source; edit canonical plugin source paths and `plugins/registry.json`.
- Managed plugins can mirror upstream source under `plugins-source/external/` when the control plane extracts bundled skills and `.mcp.json` into the normal skills and MCP flows.
- Keep repo-local skills listed in `skills/registry.json` under `unmanaged_repo_local_skills`.
- Keep `unmanaged_repo_local_skills` honest: if the target repo exists locally, the repo must contain `.agents/skills/<skill>/SKILL.md` or skill sync should fail until the stale registry entry is removed.
- Keep repo-local plugins listed in `plugins/registry.json` under `unmanaged_repo_local_plugins`.
- Do not add additional manifest files for skill mapping; update `skills/registry.json`.
- Do not add additional manifest files for plugin mapping; update `plugins/registry.json`.
- If `skills/registry.json` changes, run sync/check in the same change.
- If `plugins/registry.json` changes, run plugin sync/check in the same change.
- Do not hand-edit generated repo-local `.codex/config.toml` files in managed repos; update `codex/config/repo-bootstrap.json` and re-run the sync scripts.
- Do not hand-edit generated repo-local `.codex/agents/*.toml` files in managed repos; update `codex/config/repo-bootstrap.json` or `codex/config/agents/*.toml` and re-run the sync scripts.
- When changing shared bootstrap inputs such as `mcp/config/presets.json`, `codex/config/repo-bootstrap.json`, or repo MCP assignment, prefer `./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo <repo>` so Codex and Claude repo-local state are both re-rendered together. Use component-only Codex or Claude scripts only for intentional single-surface troubleshooting.
- If `mcp/config/presets.json` changes, run both Codex and Claude control-plane validation in the same change.
- If `agents/registry.json` changes, run both Codex and Claude control-plane validation plus `./scripts/test-control-plane.sh` in the same change.
- If `codex/config/agents/*.toml`, `codex/config/global.config.toml`, `codex/config/xcode.config.toml`, or `codex/config/repo-bootstrap.json` changes, run the Codex control-plane validation script in the same change.
