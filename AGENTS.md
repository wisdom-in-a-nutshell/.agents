# Agents Control-Plane Repo

Personal agent, Codex, and repo-local lifecycle hook control plane.

## Purpose

- Keep global skill sources and runtime links reproducible across MacBook + MacMini.
- Keep canonical personal Codex control-plane assets reproducible across MacBook + MacMini.
- Track one canonical skill registry in git.
- Keep repo-local skills in their repos unless explicitly promoted.

## Dobby System Orientation

For any control-plane, skill, hook, or repo-bootstrap change that affects Dobby
ownership, engine/workspace boundaries, dashboard/gateway flow, or more than one
Dobby repo, check
`~/GitHub/agents/skills-source/owned/dobby-system/SKILL.md` first.
Keep cross-repo Dobby orientation in that skill; keep agent control-plane
contracts in this repo's docs.

## Source of Truth

- `skills/registry.json` is the canonical skill registry.
- `plugins/registry.json` is the canonical plugin registry.
- `mcp/config/presets.json` is the canonical shared MCP registry. Per-repo assignment is the `mcp_presets` field in `codex/config/repo-bootstrap.json`; one assignment renders to both clients — Codex (`.codex/config.toml` `[mcp_servers.*]`) and Claude (per-repo `.mcp.json` at the repo root, the only project-scoped MCP file Claude Code reads). It is opt-in per repo: a repo gets `.mcp.json` only if it has `mcp_presets`.
- `hooks/registry.json` is the canonical Codex lifecycle hook registry.
- `dev-servers/registry.json` is the canonical agent-preview server registry. The shared client sync renders per-repo `.claude/launch.json` and `.codex/environments/environment.toml` from it. It is opt-in per repo: a repo gets a launch surface only if listed. Keep public Cloudflare/LaunchAgent service ports in `~/GitHub/scripts`, not this preview registry.
- `codex/` holds canonical personal Codex control-plane inputs. The Codex sync renders terminal Codex config under `~/.codex`.
- `config/global.agents.md` is the canonical machine-wide guidance source for client-specific global guidance such as `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md`.
- `config/claude-settings.json` is the canonical managed overlay of global Claude Code `settings.json` keys (`enabledPlugins` for Anthropic-bundled Claude plugins like `anthropic-skills@inline`, `skillOverrides` for bundled-skill visibility, `sshConfigs` for Claude Desktop SSH entries such as `macmini`, and `desktopPreferences` for selected Claude Desktop app preferences such as `chromeExtensionEnabled`). `scripts/sync-claude.py` merges Claude Code keys into `~/.claude/settings.json` and merges desktop preferences into `~/Library/Application Support/Claude/config.json` so this state is reproducible across machines and tracked in git. This is distinct from `plugins/registry.json` (Codex-native plugins) and `skills/registry.json` (managed standalone skills); it governs only Claude runtime surfaces those registries do not own.
- `codex/config/bundled-skills-policy.json` is the canonical policy for classifying OpenAI-bundled Codex skills that appear under `~/.codex/skills/.system` or `~/.codex/skills/codex-primary-runtime`.
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
- Codex-native plugin scope and enablement lives in `plugins/registry.json`.
- Global Codex runtime skills live in `~/.agents/skills/<skill>` as symlinks rendered from `skills/registry.json`.
- Read-only browser dashboard assets live in `dashboard/` and are served by
  `scripts/control-plane-dashboard.py`.
- Shared lifecycle hook scripts live in:
  - `hooks/scripts/`
- Shared local Git hook scripts live in:
  - `hooks/git/`

## Key Entry Points

- Apply all shared agent control planes: `./scripts/bootstrap-machine-agent-control-planes.sh --apply`
- Reconcile after git sync: `./scripts/auto-apply-agent-control-planes.sh --apply`
- Validate shared skills, plugins, Codex, and regression tests: `./scripts/check-agent-control-planes.sh`
- Audit applied local agent runtime drift for machine health checks: `./scripts/audit-agent-runtime-drift.py --plain`
- Run hermetic regression tests only: `./scripts/test-control-plane.sh`
- Bootstrap external skills/plugins through the agent-facing clients:
  - `./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo>`
  - `./scripts/bootstrap-plugin.sh <plugin-name-or-id> [--scope global|repo|dormant] [--repo <repo>]`

Detailed operations live in:

- `docs/references/agent-control-plane-operations.md`
- `docs/references/repo-lifecycle-hook-adapter.md`
- `docs/references/codex-control-plane-operations.md`
- `docs/references/cli-interface-contract.md`

## Rules

- Runtime distribution is link-first for standalone skills; Codex plugins stay native plugin entries in `plugins/registry.json`.
- Treat global skills and global plugins as a minimal default kit. For native Codex plugins, use global/manual enablement only for now; current Codex docs and runtime behavior treat plugin enablement as user-level, not reliably repo-scoped.
- When a user provides a `skills.sh` URL or upstream skill reference and wants it installed into a repo, prefer `./scripts/bootstrap-skill.sh` over manual registry edits.
- Do not edit managed skills through repo symlink destinations; edit canonical source paths.
- Do not split Codex plugins into skill or MCP registries by default. If a plugin capability should become standalone, promote it manually into `skills/registry.json` or `mcp/config/presets.json`.
- Managed plugin entries render global plugin state into `~/.codex/config.toml`; standalone skills and MCPs remain separate registries.
- A rendered native plugin entry is not the same as an installed Codex plugin package. `scripts/bootstrap-machine-agent-control-planes.sh --apply` installs missing enabled non-bundled packages through `scripts/sync-codex-plugin-installs.py`; `scripts/check-agent-control-planes.sh` runs the runtime drift audit to catch missing or stale runtime plugin state.
- Do not bootstrap native Codex plugins as repo-scoped by default. If a plugin's bundled MCP must be reliably available for one repo, promote that MCP as a standalone repo MCP preset instead of widening the whole plugin or decomposing the plugin into skills.
- Keep repo-local skills listed in `skills/registry.json` under `unmanaged_repo_local_skills`.
- Keep `unmanaged_repo_local_skills` honest: if the target repo exists locally, the repo must contain `.agents/skills/<skill>/SKILL.md` or skill sync should fail until the stale registry entry is removed.
- Keep unmanaged repo-local plugins listed in `plugins/registry.json` under `unmanaged_repo_local_plugins`.
- Do not add additional manifest files for skill mapping; update `skills/registry.json`.
- Do not add additional manifest files for plugin mapping; update `plugins/registry.json`.
- New or promoted agent-facing CLI clients must follow `docs/references/cli-interface-contract.md`.
- Do not hand-edit rendered runtime hook files. Update `hooks/registry.json` or `hooks/scripts/*`, then rerun the shared bootstrap/check.
- Repo lifecycle hook authoring contract lives in `docs/references/repo-lifecycle-hook-adapter.md`.
- Repo-specific lifecycle behavior belongs in optional Python scripts under `scripts/hooks/session_start.py`, `scripts/hooks/user_prompt_submit.py`, and explicit finalization policy at `scripts/hooks/finalize_codex_thread.py`.
- Managed repos get rendered repo-local hook config at `.codex/hooks.json` according to `hooks/registry.json`; do not hand-edit that surface. Update `hooks/registry.json`, `hooks/scripts/*`, or `codex/config/repo-bootstrap.json`, then rerun the shared bootstrap wrapper.
- Managed repos use local Git `core.hooksPath` pointing at `hooks/git/`; the shared commit-time hook delegates to repo-owned `scripts/check-fast.sh` when present.
- Use `scripts/check-fast.sh` as the fast, deterministic, repo-owned validation entrypoint. Prefer staged/affected checks there; keep slower repo-wide validation in `scripts/check-full.sh`.
- If `skills/registry.json` changes, run sync/check in the same change.
- If `plugins/registry.json` changes, run plugin sync/check in the same change.
- Do not hand-edit generated repo-local `.codex/config.toml` files in managed repos; update `codex/config/repo-bootstrap.json` and re-run the sync scripts.
- Do not hand-edit generated repo-local `.codex/hooks.json` files in managed repos; update `hooks/registry.json` and re-run the sync scripts.
- Do not hand-edit generated repo-local `.claude/launch.json` or `.codex/environments/environment.toml` files in managed repos; update `dev-servers/registry.json` and re-run `scripts/sync-claude.sh`.
- Do not hand-edit generated repo-local `.mcp.json` files in managed repos; that surface is rendered from `mcp/config/presets.json` plus the repo's `mcp_presets` in `codex/config/repo-bootstrap.json`. Update those registries and re-run the shared bootstrap/check.
- When a new OpenAI-bundled Codex skill appears locally, classify it in `codex/config/bundled-skills-policy.json` as either `allowed` or `disabled`; do not leave it as untracked local runtime drift.
- When changing shared bootstrap inputs such as `mcp/config/presets.json`, `codex/config/repo-bootstrap.json`, or repo MCP assignment, prefer `./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo <repo>` so Codex runtime and repo-local Codex hook state are re-rendered together. Use component-only scripts only for intentional single-surface troubleshooting.
- If `mcp/config/presets.json` or a repo's `mcp_presets` assignment changes, run Codex control-plane validation and the Claude sync/check (`scripts/sync-claude.sh`) in the same change, since the assignment now renders to both clients. Note: the Codex repo-config sync's `--repo` filter matches an exact path (`--repo ~/GitHub/<repo>`), not a bare repo name, so verify both `.codex/config.toml` and `.mcp.json` actually re-rendered for the target repo.
- If `hooks/registry.json`, `hooks/scripts/*`, `hooks/git/*`, or `scripts/sync-managed-git-hooks.sh` changes, run shared bootstrap/check plus `./scripts/test-control-plane.sh` in the same change.
- If `codex/config/global.config.toml` or `codex/config/repo-bootstrap.json` changes, run the Codex control-plane validation script in the same change.
- Do not hand-edit `enabledPlugins`, `skillOverrides`, or managed `sshConfigs` in the global `~/.claude/settings.json`; do not hand-edit managed `desktopPreferences` in `~/Library/Application Support/Claude/config.json`. That state is rendered from `config/claude-settings.json`. Update the overlay, then rerun the shared bootstrap/check (`./scripts/sync-claude.sh --apply` or the bootstrap wrapper). To disable an Anthropic-bundled Claude plugin set its `enabledPlugins` entry to `false`; to hide a bundled Claude skill from model context set its `skillOverrides` entry to `name-only` (still typable) or `off`.
