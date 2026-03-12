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
- Apply only the managed Codex config:
  - [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - `~/.agents/codex/scripts/sync-config.sh --apply`
- Sync exact trusted repo roots into terminal + Xcode Codex config:
  - [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - `~/.agents/codex/scripts/sync-trusted-projects.sh --apply`
- Sync repo-local `.codex/config.toml` files from the canonical registry:
  - [`sync-repo-codex-configs.sh`](/Users/adi/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - `~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply`
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
  - keeps the repo list and MCP/model preset definitions in [`repo-bootstrap.json`](/Users/adi/.agents/codex/config/repo-bootstrap.json)
- [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - runs config sync
  - runs trusted-project sync
  - runs repo-local Codex config sync
  - runs Ghostty config reconciliation
- [`configure-ghostty-cwd.sh`](/Users/dobby/.agents/codex/scripts/configure-ghostty-cwd.sh)
  - ensures Ghostty uses the Codex startup wrapper
  - ensures shell integration stays on
  - installs the `Cmd+Shift+G` picker keybind

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
