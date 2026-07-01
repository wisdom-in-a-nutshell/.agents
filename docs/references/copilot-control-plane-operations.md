# Copilot Control Plane Operations

Use this page for the GitHub Copilot client surface managed by `~/GitHub/agents`.

## Scope

The current Copilot control plane is client-first:

- Managed: terminal Copilot CLI settings, trusted folders, user-level hooks, and `~/bin/copilot`.
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
