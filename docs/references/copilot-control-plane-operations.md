# Copilot Control Plane Operations

Use this page for the GitHub Copilot client surface managed by `~/GitHub/agents`.

## Scope

The current Copilot control plane is client-first:

- Managed: terminal Copilot CLI settings, trusted folders, user-level hooks, `~/bin/copilot`, and the GitHub Copilot app's per-repo preview config.
- Observed: GitHub Copilot macOS app bundled skills under `~/Library/Application Support/com.github.githubapp/app-skills`.
- Intentionally observed only: Copilot app bundled skill visibility. The app owns its bundled skill install surface.

## Source Of Truth

- `config/copilot-settings.json`
  - scalar settings merged into `~/.copilot/settings.json`
  - trust policy rendered into `~/.copilot/config.json` `trustedFolders`
  - terminal launcher defaults rendered to `~/bin/copilot`
  - skill-noise policy for validation
- `hooks/registry.json`
  - Copilot-supported hooks render into `~/.copilot/hooks/agents-control-plane.json`
  - repo-scoped hooks render into the user hook file with a repo allowlist
- `dev-servers/registry.json`
  - GitHub Copilot app Run/browser-preview config renders into repo `.github/github-app.yml`
  - Claude Code and Codex preview config render from the same registry through `scripts/sync-claude.sh`

## Runtime Outputs

- `~/.copilot/settings.json`
  - `askUser: false`
  - `effortLevel: high`
  - quiet banner/beep/tips/notification defaults
  - no managed `trustedFolders` key; the installed CLI migrates trust to `config.json`
- `~/.copilot/config.json`
  - Copilot-managed login/session keys are preserved
  - `trustedFolders` includes `~/GitHub`, direct child repos, `~/.agents`, and `~/GitHub/agents`
  - managed trust is kept out of `settings.json` so the CLI does not move it on every startup
- `~/.copilot/hooks/agents-control-plane.json`
  - uses PascalCase event names so Copilot provides VS Code-compatible snake_case payloads
  - renders `SessionStart`, `UserPromptSubmit`, and `Stop` from the shared hook registry
  - repo-scoped hook commands include `--repos <repo-list>` and no-op outside those repos
- `~/bin/copilot`
  - wraps the real CLI at `/opt/homebrew/bin/copilot`
  - injects `--yolo --no-ask-user --effort high --mode autopilot --max-autopilot-continues 10` for normal sessions
  - does not inject defaults for management commands such as `copilot skill list`, `copilot mcp list`, `copilot login`, or `copilot version`
  - can be bypassed with `COPILOT_DISABLE_MANAGED_DEFAULTS=1`
- repo `.github/github-app.yml`
  - generated only for repos listed in `dev-servers/registry.json`
  - contains only `scripts.run`, `server_ready_pattern`, and `auto_open_in_browser`
  - intentionally does not contain `instructions`, `.github/skills`, app hooks, or `auto_approve`; current app evidence shows `auto_approve` is app/session state, not a repo-config key
  - uses the shared `scripts/run-agent-preview-server.py` wrapper so a busy fixed port is reused or rejected consistently

## Skill Policy

Do not copy managed skills into `.github/skills` or `~/.copilot/skills` by default.

Copilot already discovers:

- project skills from `.agents/skills`
- project skills from `.claude/skills`
- personal skills from `~/.agents/skills`
- app-bundled skills from the macOS app support directory

The managed check fails if direct skill copies appear under:

- `~/.copilot/skills/*/SKILL.md`
- any managed workspace repo `.github/skills/*/SKILL.md`

This keeps Copilot from loading extra duplicate skill layers. The macOS app's bundled skill directory is observed and allowlisted by name; new app-bundled skills fail the check until reviewed and added to `config/copilot-settings.json` or disabled in app settings.

## Hooks

Copilot has its own `hooks` and `disableAllHooks` settings. This repo renders a user-level hook file instead of repo `.github/hooks` files.

Reasons:

- User-level hooks run only in the local CLI/app environment where `~/GitHub/agents` exists.
- Repo `.github/hooks` files also run in Copilot cloud agent, where local machine paths would be invalid.
- PascalCase hook event names give the shared adapter snake_case payloads (`SessionStart`, `UserPromptSubmit`, `Stop`).
- `UserPromptSubmit` output is intentionally ignored for Copilot because GitHub's hook reference says that event has no output behavior.

## Commands

```bash
cd ~/GitHub/agents
./scripts/sync-copilot.sh --apply
./scripts/sync-copilot.sh --check
./scripts/bootstrap-machine-agent-control-planes.sh --apply
./scripts/check-agent-control-planes.sh
```

## App Notes

The GitHub Copilot macOS app uses the same `~/.copilot` directory for settings/logs/session state, but it also loads app-bundled skills from:

```text
~/Library/Application Support/com.github.githubapp/app-skills
```

The check reports those app-bundled skill names as observed state. It does not move, delete, or symlink that directory.

The app-specific repo config file is `.github/github-app.yml`. Public GitHub docs do not currently publish the full YAML schema; the managed renderer sticks to keys observed in the installed app parser and confirmed by the app UI: run scripts, server-ready pattern, and browser auto-open. GitHub cloud-agent environment setup remains separate (`.github/workflows/copilot-setup-steps.yml`) and is not managed here.

## App Autonomy Model (2026-07-01 finding)

The GitHub Copilot app is a separate process from the terminal CLI. It spawns its own cached engine at `~/Library/Caches/github-copilot-sdk/cli/<version>/copilot --server --stdio`, never through `~/bin/copilot`. The launcher's injected `--yolo --mode autopilot` flags cannot reach it. Confirmed by both local inspection and GitHub's own docs:

- **Permission bypass is already the default.** `~/.copilot/data.db` (`projects` and `sessions` tables) has `auto_approve INTEGER NOT NULL DEFAULT 1`. Every existing project and session in this install already has `auto_approve = 1`. Nothing to configure here.
- **There is no persisted default session mode (Interactive/Plan/Autopilot).** Confirmed by: the `data.db` schema (no `default_mode` column anywhere), the CLI's own `copilot help config` (no mode-related key), the app's NSUserDefaults plist (`~/Library/Preferences/com.github.githubapp.plist`, unrelated window-geometry keys only), and three official GitHub docs — [agent-sessions](https://docs.github.com/en/copilot/how-tos/github-copilot-app/agent-sessions) ("set the mode from the dropdown... and change it at any time"), [about-copilot-cli](https://docs.github.com/copilot/concepts/agents/about-copilot-cli), and [CLI autopilot](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/autopilot) ("runtime activation only... no mention of default settings or persistent configuration"). GitHub has not shipped a config surface for this; it is not a gap in this repo's control plane.
- **Do not hand-edit `~/.copilot/data.db` to work around this.** It is live app state (WAL-mode SQLite, not a rendered artifact) written by the app's own process while it runs. Mutating existing rows would not change what the app writes for new sessions/projects going forward, since the app's own code — not a stored default — decides those values at creation time.
- Practical upshot: pick "Autopilot" from the per-session dropdown each time; `auto_approve` (the part that actually removes approval friction) is already on.
