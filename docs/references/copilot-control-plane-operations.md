# Copilot Control Plane Operations

Use this page for the GitHub Copilot client surface managed by `~/GitHub/agents`.

## Scope

The current Copilot control plane is client-first:

- Managed: terminal Copilot CLI settings, trusted folders, and `~/bin/copilot`.
- Observed: GitHub Copilot macOS app bundled skills under `~/Library/Application Support/com.github.githubapp/app-skills`.
- Intentionally not managed yet: Copilot app bundled skill quarantine and Copilot lifecycle hooks.

## Source Of Truth

- `config/copilot-settings.json`
  - scalar settings merged into `~/.copilot/settings.json`
  - trust policy merged into `~/.copilot/config.json`
  - terminal launcher defaults rendered to `~/bin/copilot`
  - skill-noise policy for validation

## Runtime Outputs

- `~/.copilot/settings.json`
  - `askUser: false`
  - `effortLevel: high`
  - quiet banner/beep/tips/notification defaults
- `~/.copilot/config.json`
  - Copilot-managed login/session keys are preserved
  - `trustedFolders` is merged with `~/GitHub`, direct child repos, `~/.agents`, and `~/GitHub/agents`
- `~/bin/copilot`
  - wraps the real CLI at `/opt/homebrew/bin/copilot`
  - injects `--yolo --no-ask-user --effort high` for normal sessions
  - does not inject defaults for management commands such as `copilot skill list`, `copilot mcp list`, `copilot login`, or `copilot version`
  - can be bypassed with `COPILOT_DISABLE_MANAGED_DEFAULTS=1`

## Skill Policy

Do not copy managed skills into `.github/skills` or `~/.copilot/skills` by default.

Copilot already discovers:

- project skills from `.agents/skills`
- project skills from `.claude/skills`
- personal skills from `~/.agents/skills`
- app-bundled skills from the macOS app support directory

The managed check fails if direct skill copies appear under `~/.copilot/skills/*/SKILL.md`. This keeps Copilot from loading an extra duplicate skill layer.

## Hooks

Copilot has its own `hooks` and `disableAllHooks` settings, but this repo does not yet render Copilot lifecycle hooks.

Reasons:

- Codex and Claude hooks here use known local runtime schemas and payload adapters.
- Copilot app and CLI hook behavior needs a separate schema/payload compatibility pass before sharing the Stop/session hook conveyor.
- Terminal Copilot works without those hooks because `~/bin/copilot` supplies YOLO defaults and managed Git hooks still protect commits.

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
