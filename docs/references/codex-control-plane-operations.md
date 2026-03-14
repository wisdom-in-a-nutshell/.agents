# Codex Control Plane Operations

Use this page when you need the exact facts for changing or validating the personal Codex control plane.

Use [Codex Control Plane](/Users/dobby/.agents/docs/architecture/codex-control-plane.md) for the high-level system shape.
Use [Codex Control Plane Script Flows](/Users/dobby/.agents/docs/architecture/codex-control-plane-script-flows.md) for smaller diagrams of the main script groups.
Use [Codex Control Plane Ownership](/Users/dobby/.agents/docs/references/codex-control-plane-ownership.md) for the exact keep/move/generate split.

## What Lives Where

- `~/.agents`
  - canonical Codex control-plane source
  - config templates in [`codex/config/`](/Users/dobby/.agents/codex/config)
  - Codex-specific scripts in [`codex/scripts/`](/Users/dobby/.agents/codex/scripts)
  - Codex shell fragment in [`codex/shell/codex-shell.zsh`](/Users/dobby/.agents/codex/shell/codex-shell.zsh)
- `~/GitHub/scripts`
  - generic machine bootstrap and shared shell glue
  - shared zshrc in [`setup/codex/zshrc.shared`](/Users/dobby/GitHub/scripts/setup/codex/zshrc.shared)
  - machine bootstrap entrypoint in [`setup/bootstrap-machine.sh`](/Users/dobby/GitHub/scripts/setup/bootstrap-machine.sh)
- `~/.codex`
  - live runtime home only
  - applied `config.toml`, auth, sessions, logs, caches, sqlite, shell snapshots
  - Codex-managed vendor imports in `vendor_imports/`, including the nested Git checkout at `vendor_imports/skills`
  - should not be a git repo

## Canonical Commands

- Apply the full Codex bootstrap batch:
  - [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - `~/.agents/codex/scripts/bootstrap-machine-codex.sh --apply`
- Auto-apply the Codex control plane after `~/.agents` sync when `codex/` changed:
  - [`auto-apply-codex-control-plane.sh`](/Users/adi/.agents/codex/scripts/auto-apply-codex-control-plane.sh)
  - `~/.agents/codex/scripts/auto-apply-codex-control-plane.sh --apply`
- Apply only the managed Codex config:
  - [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - `~/.agents/codex/scripts/sync-config.sh --apply`
  - this also syncs managed agent-role config files into the live runtime `agents/` folders
- Sync exact trusted repo roots into terminal + Xcode Codex config:
  - [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - `~/.agents/codex/scripts/sync-trusted-projects.sh --apply`
- Sync repo-local `.codex/config.toml` files from the canonical registry:
  - [`sync-repo-codex-configs.sh`](/Users/adi/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - `~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply`
- Regenerate the Obsidian Base artifacts for the repo bootstrap registry:
  - [`sync-repo-bootstrap-registry.sh`](/Users/adi/.agents/codex/scripts/sync-repo-bootstrap-registry.sh)
  - `~/.agents/codex/scripts/sync-repo-bootstrap-registry.sh`
- Link the shared shell config:
  - [`link-shared-zshrc.sh`](/Users/dobby/GitHub/scripts/setup/codex/link-shared-zshrc.sh)
  - `~/GitHub/scripts/setup/codex/link-shared-zshrc.sh --apply`

## Healthy State Checklist

- `~/.codex` is runtime-only:
  - `git -C ~/.codex rev-parse --git-dir` should fail
- `~/.zshrc` points at the shared tracked shell file:
  - `readlink ~/.zshrc`
  - expected target: `~/GitHub/scripts/setup/codex/zshrc.shared`
- Ghostty points at the canonical Codex startup wrapper:
  - `initial-command = direct:$HOME/.agents/codex/scripts/ghostty-codex-then-shell.sh`
- `~/.codex/config.toml` uses the local machine notify path:
  - `notify = ["python3", "$HOME/.agents/codex/scripts/notify.py"]`
- `~/.codex/config.toml` and Xcode Codex config contain exact trusted repo entries for local repos such as `focus`
- `~/.codex/config.toml` contains no Git conflict markers
- `~/.codex/vendor_imports/skills` is a valid Git checkout:
  - `git -C ~/.codex/vendor_imports/skills rev-parse --show-toplevel`

## Main Scripts And Jobs

- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - applies canonical Codex config templates into live terminal + Xcode config
  - syncs canonical role config files for managed multi-agent roles into the live runtime `agents/` directories
  - rewrites machine-specific notify and system-skill paths for the current `$HOME`
  - strips foreign-user project and system-skill entries before writing
  - fails fast if the target config contains unresolved Git conflict markers
- [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - scans repo roots from the canonical repo bootstrap registry (defaults to `~/GitHub`)
  - includes explicit extra managed repos such as `~/.agents`
  - writes exact `[projects."<path>"] trust_level = "trusted"` entries
- [`sync-repo-codex-configs.sh`](/Users/adi/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - renders managed repo-local `.codex/config.toml` files from the canonical registry
  - writes minimal config files for all managed repos, with MCP presets only where assigned
  - stores backups under `~/.local/state/codex-control-plane/repo-config-backups/` instead of dirtying the git repos themselves
  - keeps the repo list and MCP/model preset definitions in [`repo-bootstrap.json`](/Users/adi/.agents/codex/config/repo-bootstrap.json)
- [`sync-repo-bootstrap-registry.sh`](/Users/adi/.agents/codex/scripts/sync-repo-bootstrap-registry.sh)
  - regenerates the Obsidian Base artifacts from [`repo-bootstrap.json`](/Users/adi/.agents/codex/config/repo-bootstrap.json)
  - updates [`repo-bootstrap.base`](/Users/adi/.agents/codex/config/repo-bootstrap.base) and [`repo-bootstrap-items/`](/Users/adi/.agents/codex/config/repo-bootstrap-items)
- [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - runs config sync
  - runs trusted-project sync
  - runs repo-local Codex config sync
  - runs Ghostty config reconciliation
- [`auto-apply-codex-control-plane.sh`](/Users/adi/.agents/codex/scripts/auto-apply-codex-control-plane.sh)
  - checks whether `~/.agents/codex/` changed since the last successful reconcile on that machine
  - runs [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh) only when a new Codex control-plane revision needs to be applied
  - stores a machine-local reconcile stamp under `~/.local/state/codex-control-plane/`
- [`configure-ghostty-cwd.sh`](/Users/dobby/.agents/codex/scripts/configure-ghostty-cwd.sh)
  - ensures Ghostty uses the Codex startup wrapper
  - ensures shell integration stays on
  - installs the `Cmd+Shift+G` current-terminal picker keybind
- [`codex-shell.zsh`](/Users/adi/.agents/codex/shell/codex-shell.zsh)
  - `codex_jump` sets the Ghostty tab/surface title to the selected repo basename before launching Codex
  - `codex_jump` also reports the selected cwd back to Ghostty immediately so regular new tabs and splits inherit the active repo instead of falling back to `~`
  - records the active Ghostty/Codex working directory to `~/.local/state/codex-control-plane/ghostty-last-dir.txt` so cold Ghostty launches can resume there
- [`ghostty-codex-then-shell.sh`](/Users/adi/.agents/codex/scripts/ghostty-codex-then-shell.sh)
  - reports the current cwd and repo basename title before the first-surface Codex launch so Ghostty new-window inheritance can reuse the active repo
  - restores the last recorded working directory on cold Ghostty launches when startup otherwise lands in `~`
- [`open-ghostty-codex-picker-tab.sh`](/Users/adi/.agents/codex/scripts/open-ghostty-codex-picker-tab.sh)
  - opens a new Ghostty tab with a custom surface configuration and immediately runs `codex_jump`
  - is the one tracked helper used by both the Stadia controller `Share` action and the optional manual Keyboard Maestro `Cmd+Shift+T` macro
- [`open-ghostty-plain-shell-split.sh`](/Users/adi/.agents/codex/scripts/open-ghostty-plain-shell-split.sh)
  - opens a Ghostty split with `CODEX_DISABLE_AUTOSTART=1` so the new pane is a plain shell in the inherited cwd
  - is intended for an optional Keyboard Maestro plain-shell split shortcut such as `Cmd+Opt+D`

## Repo Bootstrap Registry Fields

- [`repo-bootstrap.json`](/Users/adi/.agents/codex/config/repo-bootstrap.json) currently controls these per-repo fields:
  - `mcp_presets`
  - `model`
  - `model_reasoning_effort`
  - `service_tier`
  - `notes`
- The global defaults block supplies fallback values for repos that do not override them.

## Automatic Cross-Machine Apply

- Launchd still lives in [`~/GitHub/scripts/sync/git-auto-sync.sh`](/Users/adi/GitHub/scripts/sync/git-auto-sync.sh), because scheduler ownership is part of the generic machine-ops repo.
- Codex-specific post-sync apply logic lives in [`auto-apply-codex-control-plane.sh`](/Users/adi/.agents/codex/scripts/auto-apply-codex-control-plane.sh), because the apply contract is Codex-specific policy.
- Practical flow:
  1. one machine pushes a change in `~/.agents`
  2. the other machine pulls it on the next git auto-sync cycle
  3. `git-auto-sync.sh` calls `auto-apply-codex-control-plane.sh`
  4. that script runs `bootstrap-machine-codex.sh --apply` only when `~/.agents/codex/` changed
- Result:
  - no daily manual Codex bootstrap is needed on healthy machines
  - offline machines catch up on the next successful sync after they come online

## Known Failure Modes

### Conflict Markers In `config.toml`

Symptom:
- Codex prints `key with no value, expected '='`
- lines in `config.toml` include `<<<<<<<`, `=======`, or `>>>>>>>`

Meaning:
- a prior sync/pull left unresolved Git conflict markers in the live config

Current protection:
- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh) now refuses to run against a config containing conflict markers

Fix:
- remove the conflict block from the live config
- rerun `~/.agents/codex/scripts/bootstrap-machine-codex.sh --apply`

### Foreign Absolute Paths In Live Config

Symptom:
- a machine under `/Users/adi` contains `/Users/dobby/...` paths, or vice versa

Meaning:
- machine-specific config entries were preserved from another machine

Current protection:
- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh) now rewrites local notify/system-skill paths and strips foreign-user project entries before applying

Fix:
- rerun `~/.agents/codex/scripts/bootstrap-machine-codex.sh --apply`

### Repeated Trust Prompts For Nested Repos

Symptom:
- Codex keeps asking whether a repo like `~/GitHub/focus` is trusted

Meaning:
- the exact repo root is missing from `[projects.*]`, even if a parent path is trusted

Fix:
- rerun `~/.agents/codex/scripts/sync-trusted-projects.sh --apply`

### Stale Snapshot-Refresh LaunchAgent

Symptom:
- `launchctl print gui/$(id -u)/com.<user>.codex-app-server-snapshot-refresh` shows a scheduled job with `last exit code = 78`
- the job points at `~/.agents/scripts/refresh-codex-app-server-readme-reference.sh`
- that script path no longer exists

Meaning:
- this is leftover machine state from the older Codex App Server snapshot-refresh automation
- the automation was removed, so recreating the missing script is the wrong fix

Fix:
- unload and delete the stale LaunchAgent plist:
- `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.$USER.codex-app-server-snapshot-refresh.plist >/dev/null 2>&1 || true`
- `rm -f ~/Library/LaunchAgents/com.$USER.codex-app-server-snapshot-refresh.plist`

### Recommended Skills Fail To Load

Symptom:
- Codex App shows `Unable to load recommended skills`
- message says `Expected ~/.codex/vendor_imports/skills to be a git checkout but found an existing directory`

Meaning:
- the runtime-managed checkout under `~/.codex/vendor_imports/skills` was deleted or flattened into a plain directory

Fix:
- restore `~/.codex/vendor_imports/skills` as a real clone of `https://github.com/openai/skills.git`
- verify with `git -C ~/.codex/vendor_imports/skills rev-parse --show-toplevel`
- restart Codex App if it is already open

## Machine Notes

- Both current machines were aligned through this control-plane layout:
  - local machine under `/Users/dobby`
  - MacBook via SSH alias `macbook-wan` under `/Users/adi`
- The control plane is designed to be home-relative at apply time, not by committing one machine's absolute paths into canonical templates.
