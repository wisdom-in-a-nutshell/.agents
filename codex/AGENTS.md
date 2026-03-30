# Codex Control Plane

Canonical personal Codex control-plane assets live here.

## Purpose

- Keep synced, durable Codex configuration under `~/.agents`.
- Keep `~/GitHub/scripts` as the machine bootstrap/apply shell, not the long-term owner of Codex policy.
- Keep `~/.codex` as the applied runtime home.
- Keep Codex-adjacent terminal workflow behavior here when it exists to drive Codex, even if the trigger surface is Ghostty or Keyboard Maestro.

## Layout

- `config/`: canonical Codex config fragments and templates.
  - `config/global.agents.md`: canonical machine-wide guidance source for `~/.codex/AGENTS.md`.
  - `config/agents/*.toml`: canonical multi-agent role config files synced into live Codex runtimes.
- `scripts/`: canonical Codex-specific automation scripts.
  - includes Ghostty/Codex helper scripts and any thin helper invoked by Keyboard Maestro for Codex workflows.
- `shell/`: Codex-specific shell and Ghostty integration fragments.

## Rules

- Do not store auth, session history, caches, logs, runtime databases, or secrets here.
- If a script must run from `~/.codex` or another runtime path, keep the canonical source here and sync or point to it from the runtime config.
- Prefer repo-local `.codex/config.toml` for project-specific MCP/tool behavior instead of putting repo policy here.
- Keep mixed shell-dotfile concerns out of this folder until they are cleanly split from Codex-only behavior.
- Treat `~/.codex/vendor_imports/` as Codex-managed runtime state.
- Keep managed backup artifacts under `~/.local/state/codex-control-plane/`, not alongside live files in `~/.codex`.
- Do not delete, flatten, or "clean up" `~/.codex/vendor_imports/skills`; Codex App expects it to remain a nested Git checkout of `openai/skills`.

## Current Scope

- `scripts/sync-config.sh` is the canonical sync/apply entrypoint for machine Codex config.
- `scripts/sync-global-agents-md.sh` is the canonical sync/apply entrypoint for machine-wide `~/.codex/AGENTS.md`.
- `scripts/sync-trusted-projects.sh` is the canonical trusted-repo sync entrypoint for Codex.
- `scripts/sync-repo-codex-configs.sh` is the canonical repo-local Codex config sync/apply entrypoint.
- `scripts/bootstrap-machine-codex.sh` is the canonical Codex-specific machine bootstrap batch.
- `scripts/check-codex-control-plane.sh` is the canonical Codex control-plane validation entrypoint.
- `scripts/auto-apply-codex-control-plane.sh` is the canonical post-sync Codex reconcile entrypoint for cross-machine convergence.
- `config/global.config.toml` and `config/xcode.config.toml` are the canonical managed baselines.
- `config/agents/*.toml` are the canonical managed role overrides for built-in and custom multi-agent roles.
- `config/repo-bootstrap.json` is the canonical registry for repo-local Codex bootstrap and MCP presets.
- `scripts/sync-repo-bootstrap-registry.sh` generates the Obsidian Base artifacts for that registry.
- `config/global.agents.md` is the canonical machine-wide AGENTS content that bootstraps to `~/.codex/AGENTS.md`.
- `scripts/notify.py` is the canonical notify automation source.
- `scripts/configure-ghostty-cwd.sh` and `scripts/ghostty-codex-then-shell.sh` are the canonical Ghostty/Codex startup helpers.
- `scripts/install-sudoers-codex-ops.sh` is the canonical sudoers installer for Codex machine-ops workflows.
- `shell/codex-shell.zsh` is the Codex-specific shell fragment sourced by the shared `~/.zshrc`.

## Repo Bootstrap Registry

- `config/repo-bootstrap.json` is the one place to decide managed repo-local Codex behavior.
- Multi-agent role tuning belongs in `config/global.config.toml`, `config/xcode.config.toml`, and `config/agents/*.toml`, not in repo bootstrap.
- The current managed role setup is:
  - built-in `explorer` remains available for local repo and runtime exploration
  - managed `external_researcher` handles information outside the local repo and runtime
  - repo-scoped custom `bedrock_sonnet` is available in opted-in repos for LiteLLM/AWS Bedrock Claude Sonnet 4.6 validation and alternate-provider work
- The current per-repo control surface is:
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
- `repo-bootstrap.json` also carries `agent_presets`, which define the reusable declaration metadata for repo-scoped custom roles while the role behavior stays in `config/agents/*.toml`.
- The registry `defaults` block is rendered into every managed repo-local `.codex/config.toml` unless a repo entry overrides those keys explicitly.
- `defaults.features` is merged with per-repo `features`, so baseline feature flags can be enabled globally while still allowing repo overrides.
- `scripts/sync-repo-bootstrap-registry.sh` regenerates:
  - `../docs/references/registry/repo-bootstrap.base`
    - includes effective per-repo skill availability merged from `../skills/registry.json`
  - `../docs/references/registry/repo-bootstrap-items/`
  - `../docs/references/registry/mcp-registry.base`
  - `../docs/references/registry/mcp-registry-items/`
- `scripts/sync-repo-codex-configs.sh --apply` renders the actual repo-local `.codex/config.toml` files from that JSON registry.
- `scripts/sync-trusted-projects.sh --apply` ensures those repo-local configs are trusted and therefore loaded by Codex.
- `scripts/check-codex-control-plane.sh` validates canonical role definitions, runtime role declarations, and repo-scoped custom-agent render output after sync.
- `scripts/auto-apply-codex-control-plane.sh --apply` is the machine-local post-sync reconcile hook that runs `bootstrap-machine-codex.sh --apply` when `~/.agents/codex/` changed since the last successful reconcile.
