# Rendered Surfaces

Use this page to decide whether a file is source or output.

The control plane works by keeping canonical inputs in `~/.agents`, then rendering or linking runtime-facing files into this repo, machine runtime homes, and managed repos. If a path is listed here, do not hand-edit it as source.

## Core Rule

Edit the canonical source, run the renderer, then run the validation command.

## Surface Map

| Rendered path | Kind | Canonical source | Renderer | Validation | Hand-edit? |
| --- | --- | --- | --- | --- | --- |
| `skills/<skill>` | global runtime skill symlink | `skills/registry.json`, `skills-source/*/<skill>/` | `scripts/sync-skills-registry.sh --apply` | `scripts/check-skills-registry.sh` | No |
| `.agents/skills/<skill>` | repo-local Codex skill symlink for this repo | `skills/registry.json`, `skills-source/*/<skill>/` | `scripts/sync-skills-registry.sh --apply` | `scripts/check-agent-control-planes.sh --repo ~/.agents` | No |
| `.claude/skills/<skill>` | repo-local Claude skill symlink for this repo | `skills/registry.json`, `skills-source/*/<skill>/` | `claude/scripts/sync-skills.sh --apply --repo ~/.agents` | `claude/scripts/check-claude-control-plane.sh --repo ~/.agents` | No |
| `.codex/config.toml` | repo-local Codex config for this repo | `codex/config/repo-bootstrap.json`, `mcp/config/presets.json` | `codex/scripts/sync-repo-codex-configs.sh --apply --repo ~/.agents` | `codex/scripts/check-codex-control-plane.sh --repo ~/.agents` | No |
| `.codex/hooks.json` | repo-local Codex hook config for this repo | `hooks/registry.json`, `codex/config/repo-bootstrap.json` | `codex/scripts/sync-repo-codex-configs.sh --apply --repo ~/.agents` | `codex/scripts/check-codex-control-plane.sh --repo ~/.agents` | No |
| `.claude/settings.json` | repo-local Claude settings and hook config for this repo | `claude/config/bootstrap.json`, `codex/config/repo-bootstrap.json`, `hooks/registry.json` | `claude/scripts/sync-repo-claude-configs.sh --apply --repo ~/.agents` | `claude/scripts/check-claude-control-plane.sh --repo ~/.agents` | No |
| repo `CLAUDE.md` files | Claude compatibility import files | repo `AGENTS.md` files, `claude/config/bootstrap.json` | `claude/scripts/sync-repo-claude-configs.sh --apply --repo <repo>` | `claude/scripts/check-claude-control-plane.sh --repo <repo>` | No |
| repo `.mcp.json` files | Claude repo MCP config | `codex/config/repo-bootstrap.json`, `mcp/config/presets.json` | `claude/scripts/sync-repo-claude-configs.sh --apply --repo <repo>` | `claude/scripts/check-claude-control-plane.sh --repo <repo>` | No |
| `docs/references/registry/skills.base` and `skills-items/` | generated Obsidian skill views | `skills/registry.json` | `scripts/sync-skills-registry.sh --apply` | `scripts/check-skills-registry.sh` | No |
| `docs/references/registry/plugins.base` and `plugins-items/` | generated Obsidian plugin views | `plugins/registry.json` | `scripts/sync-plugins-registry.sh --apply` | `scripts/check-plugins-registry.sh` | No |
| `docs/references/registry/repo-bootstrap.base` and `repo-bootstrap-items/` | generated Obsidian repo views | `codex/config/repo-bootstrap.json`, `skills/registry.json` | `codex/scripts/sync-repo-bootstrap-registry.sh` | `scripts/check-skills-registry.sh` | No |
| `docs/references/registry/mcp-registry.base` and `mcp-registry-items/` | generated Obsidian MCP views | `codex/config/repo-bootstrap.json`, `mcp/config/presets.json` | `codex/scripts/sync-repo-bootstrap-registry.sh` | `scripts/check-skills-registry.sh` | No |
| `~/.codex/config.toml` | live Codex runtime config | `codex/config/*`, `mcp/config/presets.json` | `codex/scripts/sync-config.sh --apply` | `codex/scripts/check-codex-control-plane.sh` | No |
| `~/.codex/hooks.json` | live Codex global hooks; repo-assigned hooks render to repo `.codex/hooks.json` | `hooks/registry.json` | `codex/scripts/sync-config.sh --apply` | `codex/scripts/check-codex-control-plane.sh` | No |
| `~/.codex/AGENTS.md` | live Codex global guidance symlink | `codex/config/global.agents.md` | `codex/scripts/sync-global-agents-md.sh --apply` | `codex/scripts/check-codex-control-plane.sh` | No |
| `~/.claude/CLAUDE.md` | live Claude global guidance symlink | `codex/config/global.agents.md` through `claude/config/global.claude.md` | `claude/scripts/sync-global-claude-md.sh --apply` | `claude/scripts/check-claude-control-plane.sh` | No |
| `~/.claude/settings.json` | live Claude global runtime settings | `claude/config/settings.json`, `hooks/registry.json` | `claude/scripts/sync-settings.sh --apply` | `claude/scripts/check-claude-control-plane.sh` | No |
| `~/Library/LaunchAgents/com.<user>.codex-session-archiver.plist` | machine-local stale Codex session archive schedule | `codex/scripts/install-archive-stale-sessions-launchagent.sh` | `codex/scripts/install-archive-stale-sessions-launchagent.sh --apply` | `launchctl print gui/$(id -u)/com.$USER.codex-session-archiver` | No |
| managed repo `.git/config` `core.hooksPath` | machine-local Git hook config | `hooks/git/`, `codex/config/repo-bootstrap.json` | `scripts/sync-managed-git-hooks.sh --apply` | `scripts/sync-managed-git-hooks.sh --check` | No |
| managed repo `.github/hooks/agent-control-plane.json` | repo-local GitHub Copilot hook config | `hooks/registry.json`, `codex/config/repo-bootstrap.json` | `scripts/sync-copilot-hooks.sh --apply --repo <repo>` | `scripts/sync-copilot-hooks.sh --check --repo <repo>` | No |

## Canonical Source Families

- Registries: `skills/registry.json`, `plugins/registry.json`, `hooks/registry.json`, `mcp/config/presets.json`, `codex/config/repo-bootstrap.json`.
- Source content: `skills-source/`, `plugins-source/`, `hooks/scripts/`, `hooks/git/`, `codex/config/`, `claude/config/`.
- Generated lookup views: `docs/references/registry/`.
- Machine-local state and backups: `~/.local/state/...`, not tracked repo paths.

## Practical Recovery

If a rendered file looks wrong:

1. Find its canonical source in the table.
2. Change only that source.
3. Run the renderer listed in the table.
4. Run `./scripts/check-agent-control-planes.sh`.
