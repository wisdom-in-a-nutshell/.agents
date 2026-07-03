# Copilot Control Plane Operations

Use this page for the GitHub Copilot client surface managed by `~/GitHub/agents`.

## Scope

The current Copilot control plane is client-first:

- Managed: terminal Copilot CLI settings, trusted folders, user-level hooks, `~/bin/copilot`, local session cleanup, and the GitHub Copilot app's per-repo preview config.
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
- `config/global.agents.md`
  - the same canonical machine-wide guidance rendered into `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`
  - now also symlinked into `~/.copilot/copilot-instructions.md` by `scripts/sync-copilot.py`
- `scripts/prune-stale-copilot-sessions.py`
  - local-only cleanup for stale `~/.copilot/session-state/<session-id>` data plus matching `~/.copilot/session-store.db` rows
  - mirrors GitHub's documented `/session prune --older-than DAYS` behavior for automation, because `/session prune` is an interactive slash command rather than a top-level non-interactive CLI subcommand

## Runtime Outputs

- `~/.copilot/settings.json`
  - `askUser: false`
  - `effortLevel: high`
  - quiet banner/beep/tips/notification defaults
  - `ide.autoConnect: false` and `ide.openDiffOnEdit: false` so terminal Copilot sessions do not auto-connect to IDE workspaces or open IDE diffs unless `/ide` is invoked manually
  - `memory: false` so Copilot does not use cross-session agentic memory by default
  - `disabledSkills` disables noisy, rarely needed, UI-only, or Codex-App-Server-specific skills for local terminal Copilot sessions (`af`, `agent-merge`, `agentfinder`, `adi-design`, `codex-app-server`, `create-canvas`, `customize-cloud-agent`, `find-skills`, `imagegen`, `impeccable`, `media-toolkit`, `openai-docs`, `orchestrate`, `pdf`, `project`, `social-media-publishing`)
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
  - sources `~/.secrets/copilot-cli/env` when present so machines that cannot write the `copilot-cli` keychain item non-interactively can still provide `COPILOT_GITHUB_TOKEN` to the child CLI process
  - injects `--yolo --no-ask-user --model claude-sonnet-5 --effort high --mode autopilot --max-autopilot-continues 10 --disable-builtin-mcps` for normal sessions
  - disables only GitHub's broad built-in MCP server by default; repo-scoped MCPs such as `openaiDeveloperDocs` remain available when configured through managed `.mcp.json`
  - does not inject defaults for management commands such as `copilot skill list`, `copilot mcp list`, `copilot login`, or `copilot version`
  - can be bypassed with `COPILOT_DISABLE_MANAGED_DEFAULTS=1`
- repo `.github/github-app.yml`
  - generated only for repos listed in `dev-servers/registry.json`
  - contains only `scripts.run`, `server_ready_pattern`, and `auto_open_in_browser`
  - intentionally does not contain `instructions`, `.github/skills`, app hooks, or `auto_approve`; current app evidence shows `auto_approve` is app/session state, not a repo-config key
  - uses the shared `scripts/run-agent-preview-server.py` wrapper so a busy fixed port is reused or rejected consistently
  - renders `{repo_root}` through `${COPILOT_WORKSPACE_PATH:-...}` so GitHub Copilot app worktree sessions preview the active worktree while ordinary local runs fall back to the canonical `~/GitHub/<repo>` checkout
- `~/.copilot/copilot-instructions.md`
  - relative symlink to `config/global.agents.md`, the same canonical file rendered into `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`
  - gives Copilot CLI and the Copilot app the same machine-wide baseline guidance the other two clients already had; previously this path was empty and Copilot got none of it
- `~/Library/LaunchAgents/com.<user>.copilot-session-pruner.plist`
  - installed when `~/.copilot/session-state` or `~/.copilot/session-store.db` exists
  - runs hourly and prunes local Copilot sessions whose `updated_at` is older than 24 hours
  - skips session directories that contain a live `inuse.<pid>.lock`
  - writes backups under `~/.local/state/copilot-control-plane/prune-stale-copilot-sessions/backups`
  - never deletes synced GitHub.com session data

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

The managed settings overlay also writes `disabledSkills` for built-in, app-adjacent, or rarely needed personal/project skills that are available but noisy for normal local terminal sessions. `copilot skill list --json` may still report disabled skills as available; the runtime proof is the session startup summary or a prompt probe. On 2026-07-03, a prompt-mode probe reported 14 loaded skills and confirmed `customize-cloud-agent` was not loaded after `disabledSkills` included it. After tightening the list, a normal wrapper session in this repo reported only the core remaining skills. The launcher disables GitHub's built-in MCP server, but does not disable repo MCPs; if `openaiDeveloperDocs` is assigned through the repo `.mcp.json`, it remains available.

**Known blind spot (2026-07-01):** the app's own Settings → Skills → "Built-in" list does not map 1:1 to `app-skills/` on disk. `customize-cloud-agent` appears in the in-app "Built-in" list but has no folder under `app-skills/` — it is compiled into the app binary. Conversely `impeccable` exists as a loose folder under `app-skills/` (and is what this check observes) but is not shown in the app's "Built-in" tab, likely deduped against a same-named personal skill surfaced under "On this device" instead. `expectedAppBundledSkills` now includes `customize-cloud-agent` for documentation, but the check can only ever see loose `app-skills/*/SKILL.md` folders — it has no visibility into skills the app bundles internally, and cannot detect new ones added that way. Toggling a "Built-in" skill on/off in the app's Settings UI is the only control for it; no file or setting was found that persists that toggle.

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
./scripts/prune-stale-copilot-sessions.py --plain --older-than-hours 24
./scripts/install-prune-stale-copilot-sessions-launchagent.sh --apply
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

For app worktree sessions, the app exposes `COPILOT_WORKSPACE_PATH` to lifecycle scripts. The renderer uses that variable for `{repo_root}` in `.github/github-app.yml` only; Claude Code and Codex still receive the stable checkout path. If a preview needs gitignored local files inside a Copilot app worktree, add a repo-owned `.worktreeinclude` file in that repo rather than teaching this control plane to copy secrets globally.

## Local Session Cleanup

GitHub's current docs say Copilot CLI session files live under `~/.copilot/session-state/`, and structured session data lives in the local SQLite session store at `~/.copilot/session-store.db`. The documented cleanup command is the interactive slash command `/session prune --older-than DAYS`; GitHub states that `/session prune` affects local sessions only and does not delete synced GitHub.com data.

The managed `copilot-session-pruner` LaunchAgent provides the same local-only policy for unattended machine cleanup. It uses the documented local store locations, prunes stale indexed sessions plus stale unindexed `session-state` directories, skips live `inuse.<pid>.lock` sessions, and backs up before applying. It intentionally does not mutate GitHub.com synced session history; remove synced sessions through GitHub's own UI when needed.

Run a dry-run before changing the threshold:

```bash
~/GitHub/agents/scripts/prune-stale-copilot-sessions.py --plain --older-than-hours 24
```

## App Autonomy Model (2026-07-01 finding)

The GitHub Copilot app is a separate process from the terminal CLI. It spawns its own cached engine at `~/Library/Caches/github-copilot-sdk/cli/<version>/copilot --server --stdio`, never through `~/bin/copilot`. The launcher's injected `--yolo --mode autopilot` flags cannot reach it. Confirmed by both local inspection and GitHub's own docs:

- **Permission bypass is already the default.** `~/.copilot/data.db` (`projects` and `sessions` tables) has `auto_approve INTEGER NOT NULL DEFAULT 1`. Every existing project and session in this install already has `auto_approve = 1`. Nothing to configure here.
- **There is no persisted default session mode (Interactive/Plan/Autopilot).** Confirmed by: the `data.db` schema (no `default_mode` column anywhere), the CLI's own `copilot help config` (no mode-related key), the app's NSUserDefaults plist (`~/Library/Preferences/com.github.githubapp.plist`, unrelated window-geometry keys only), and three official GitHub docs — [agent-sessions](https://docs.github.com/en/copilot/how-tos/github-copilot-app/agent-sessions) ("set the mode from the dropdown... and change it at any time"), [about-copilot-cli](https://docs.github.com/copilot/concepts/agents/about-copilot-cli), and [CLI autopilot](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/autopilot) ("runtime activation only... no mention of default settings or persistent configuration"). GitHub has not shipped a config surface for this; it is not a gap in this repo's control plane.
- **Do not hand-edit `~/.copilot/data.db` to work around this.** It is live app state (WAL-mode SQLite, not a rendered artifact) written by the app's own process while it runs. Mutating existing rows would not change what the app writes for new sessions/projects going forward, since the app's own code — not a stored default — decides those values at creation time.
- Practical upshot: pick "Autopilot" from the per-session dropdown each time; `auto_approve` (the part that actually removes approval friction) is already on.
