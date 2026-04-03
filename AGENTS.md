# .agents repo

Personal agent and Codex control plane.

## Purpose

- Keep global skill sources and runtime links reproducible across MacBook + MacMini.
- Keep canonical personal Codex control-plane assets reproducible across MacBook + MacMini.
- Track one canonical skill registry in git.
- Keep repo-local skills in their repos unless explicitly promoted.

## Source of Truth

- `skills/registry.json` is the canonical skill registry.
- `mcp/config/presets.json` is the canonical shared MCP registry.
- `codex/` holds canonical personal Codex control-plane inputs.
- `codex/config/repo-bootstrap.json` is the canonical shared repo registry for managed repo-local behavior.
  - Per repo it can define:
    - `mcp_presets`
    - `custom_agents`
    - `model`
    - `model_reasoning_effort`
    - `model_verbosity`
    - `personality`
    - `model_instructions_file`
    - `project_root_markers`
    - `features`
    - `service_tier`
- Managed canonical skill content lives in:
  - `skills-source/external/<skill>/`
  - `skills-source/owned/<skill>/`
- Global runtime skills live in `skills/<skill>` as symlinks.
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

- Dry-run sync: `./scripts/sync-skills-registry.sh`
- Apply sync: `./scripts/sync-skills-registry.sh --apply`
  - Sync applies desired managed links and prunes obsolete managed global runtime links.
- Validate generated registry artifacts: `./scripts/check-skills-registry.sh`
- Dry-run external upstream refresh: `./scripts/refresh-external-skills.sh`
- Apply external upstream refresh: `./scripts/refresh-external-skills.sh --apply`
  - Refresh preserves local `agents/openai.yaml` inside external skill folders.
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
- Managed link regeneration runs every auto-sync cycle:
  - `~/.agents/scripts/sync-skills-registry.sh --apply`

## Rules

- Distribution policy is link-only.
- Treat global skills as a minimal default kit; prefer repo scope or repo-local unless a skill is broadly useful across unrelated repos.
- Do not edit managed skills through repo symlink destinations; edit canonical source paths.
- If the external global `pdf` skill remains enabled, keep its machine dependencies installed on managed Macs: `pdftoppm` from Poppler plus Python user-site packages `reportlab`, `pdfplumber`, and `pypdf`.
- Keep repo-local skills listed in `skills/registry.json` under `unmanaged_repo_local_skills`.
- Do not add additional manifest files for skill mapping; update `skills/registry.json`.
- If `skills/registry.json` changes, run sync/check in the same change.
- Do not hand-edit generated repo-local `.codex/config.toml` files in managed repos; update `codex/config/repo-bootstrap.json` and re-run the sync scripts.
- Do not hand-edit generated repo-local `.codex/agents/*.toml` files in managed repos; update `codex/config/repo-bootstrap.json` or `codex/config/agents/*.toml` and re-run the sync scripts.
- If `mcp/config/presets.json` changes, run both Codex and Claude control-plane validation in the same change.
- If `codex/config/agents/*.toml`, `codex/config/global.config.toml`, `codex/config/xcode.config.toml`, or `codex/config/repo-bootstrap.json` changes, run the Codex control-plane validation script in the same change.
