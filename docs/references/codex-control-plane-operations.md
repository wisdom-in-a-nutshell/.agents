# Codex Control Plane Operations

Use this page when you need the exact facts for changing or validating the personal Codex control plane.

Use [Codex Control Plane](/Users/dobby/.agents/docs/architecture/codex-control-plane.md) for the high-level system shape.
Use [Codex Control Plane Script Flows](/Users/dobby/.agents/docs/architecture/codex-control-plane-script-flows.md) for smaller diagrams of the main script groups.
Use [Codex Control Plane Ownership](/Users/dobby/.agents/docs/references/codex-control-plane-ownership.md) for the exact keep/move/generate split.

## What Lives Where

- `~/.agents`
  - canonical Codex control-plane source
  - config templates in [`codex/config/`](/Users/dobby/.agents/codex/config)
  - bundled Codex skill allow/disable policy in [`codex/config/bundled-skills-policy.json`](/Users/dobby/.agents/codex/config/bundled-skills-policy.json)
  - Codex-specific scripts in [`codex/scripts/`](/Users/dobby/.agents/codex/scripts)
  - Codex shell fragment in [`codex/shell/codex-shell.zsh`](/Users/dobby/.agents/codex/shell/codex-shell.zsh)
- `~/GitHub/scripts`
  - generic machine bootstrap and shared shell glue
  - shared zshrc in [`setup/codex/zshrc.shared`](/Users/dobby/GitHub/scripts/setup/codex/zshrc.shared)
  - shared zprofile in [`setup/codex/zprofile.shared`](/Users/dobby/GitHub/scripts/setup/codex/zprofile.shared)
  - machine bootstrap entrypoint in [`setup/bootstrap-machine.sh`](/Users/dobby/GitHub/scripts/setup/bootstrap-machine.sh)
- `~/.codex`
  - live runtime home only
  - applied `config.toml`, global `hooks.json`, auth, sessions, logs, caches, sqlite, shell snapshots
  - global Codex hooks such as `Stop` live in `~/.codex/hooks.json`; repo-specific context hooks live in managed repo `.codex/hooks.json`
  - Codex-managed vendor imports in `vendor_imports/`, including the nested Git checkout at `vendor_imports/skills`
  - should not be a git repo
- `~/.local/state/codex-control-plane`
  - machine-local reconcile stamps and quarantine state

## Canonical Commands

- Apply the shared machine-facing agent bootstrap batch:
  - [`bootstrap-machine-agent-control-planes.sh`](/Users/dobby/.agents/scripts/bootstrap-machine-agent-control-planes.sh)
  - `~/.agents/scripts/bootstrap-machine-agent-control-planes.sh --apply`
  - this syncs managed skill links, native Codex plugin state, repo-local hook files, and the Codex runtime control plane from one stable root entrypoint
- Auto-apply the shared agent control plane after `~/.agents` sync when runtime-relevant files changed:
  - [`auto-apply-agent-control-planes.sh`](/Users/dobby/.agents/scripts/auto-apply-agent-control-planes.sh)
  - `~/.agents/scripts/auto-apply-agent-control-planes.sh --apply`
  - this is the machine-facing post-sync entrypoint that external bootstrap repos should call
- Enroll top-level GitHub repos into the managed repo bootstrap registry:
  - [`enroll-managed-repos.sh`](/Users/dobby/.agents/scripts/enroll-managed-repos.sh)
  - `~/.agents/scripts/enroll-managed-repos.sh --apply --github-root ~/GitHub`
  - this scans only direct child Git repos under the GitHub root and adds missing minimal entries to [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
- Validate shared skills, plugins, repo-local hook files, and Codex rendered runtime state:
  - [`check-agent-control-planes.sh`](/Users/dobby/.agents/scripts/check-agent-control-planes.sh)
  - `~/.agents/scripts/check-agent-control-planes.sh`
- Validate managed plugins:
  - [`sync-plugins-registry.sh`](/Users/dobby/.agents/scripts/sync-plugins-registry.sh)
  - `~/.agents/scripts/sync-plugins-registry.sh --apply`
  - global native Codex plugin enable/disable state is rendered by `sync-config.sh`; repo-scoped native plugin assignments are rendered by `sync-repo-codex-configs.sh`
- Bootstrap one managed plugin into the canonical registry:
  - [`bootstrap-plugin.sh`](/Users/dobby/.agents/scripts/bootstrap-plugin.sh)
  - `~/.agents/scripts/bootstrap-plugin.sh build-ios-apps --apply`
  - this writes the registry entry, validates it, and reapplies the shared control planes
- Apply the full Codex bootstrap batch:
  - [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - `~/.agents/codex/scripts/bootstrap-machine-codex.sh --apply`
  - this applies the Codex control-plane outputs only, including the stale-thread finalization LaunchAgent; shared shell links still come from `~/GitHub/scripts/setup/codex/`
- Check stale Codex threads without finalizing:
  - [`finalize-stale-codex-threads.py`](/Users/dobby/.agents/codex/scripts/finalize-stale-codex-threads.py)
  - `~/.agents/codex/scripts/finalize-stale-codex-threads.py --dry-run --older-than-days 2`
  - eligibility is based on Codex `thread.updatedAt`, not creation time
- Check stale Codex Desktop sidebar projects without changing state:
  - [`prune-sidebar-projects.py`](/Users/dobby/.agents/codex/scripts/prune-sidebar-projects.py)
  - `~/.agents/codex/scripts/prune-sidebar-projects.py --plain`
  - for a MacBook sidebar showing Mac mini remote projects, add `--remote-host macmini`; use `--no-unsaved-thread-projects` when pruning only saved/remote sidebar entries
- Install/update the stale-thread finalization LaunchAgent:
  - [`install-finalize-stale-codex-threads-launchagent.sh`](/Users/dobby/.agents/codex/scripts/install-finalize-stale-codex-threads-launchagent.sh)
  - `~/.agents/codex/scripts/install-finalize-stale-codex-threads-launchagent.sh --apply`
  - default schedule is every 6 hours, finalizing managed-repo threads whose last update is older than 48 hours
- Install/update the nightly sidebar project prune LaunchAgent:
  - [`install-sidebar-project-prune-launchagent.sh`](/Users/dobby/.agents/codex/scripts/install-sidebar-project-prune-launchagent.sh)
  - `~/.agents/codex/scripts/install-sidebar-project-prune-launchagent.sh --apply`
  - default schedule is 01:00 daily; it quits Codex, prunes stale sidebar state, then reopens Codex so the app does not rewrite the old in-memory sidebar list
  - on a MacBook showing Mac mini remote projects, use `--remote-host macmini --no-unsaved-thread-projects`
  - install this only on machines where the restart behavior is wanted; it is not part of the default bootstrap batch
- Auto-apply the Codex control plane after `~/.agents` sync when `codex/` changed:
  - [`auto-apply-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/auto-apply-codex-control-plane.sh)
  - `~/.agents/codex/scripts/auto-apply-codex-control-plane.sh --apply`
  - use this for targeted Codex-only troubleshooting or component-scoped automation, not as the machine-facing shared reconcile entrypoint
- Apply only the managed Codex config:
  - [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - `~/.agents/codex/scripts/sync-config.sh --apply`
  - this syncs the managed global config, global `hooks.json`, and removes stale managed agent-role files from older control-plane versions
- Validate canonical and rendered Codex control-plane state:
  - [`check-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/check-codex-control-plane.sh)
  - `~/.agents/codex/scripts/check-codex-control-plane.sh`
- Sync exact trusted repo roots into the global Codex config:
  - [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - `~/.agents/codex/scripts/sync-trusted-projects.sh --apply`
- Sync repo-local `.codex/config.toml` and `.codex/hooks.json` files from the canonical registries:
  - [`sync-repo-codex-configs.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - `~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply`
- Validate the repo bootstrap registry:
  - [`sync-repo-bootstrap-registry.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-bootstrap-registry.sh)
  - `~/.agents/codex/scripts/sync-repo-bootstrap-registry.sh`
- Link the shared shell config:
  - [`link-shared-zshrc.sh`](/Users/dobby/GitHub/scripts/setup/codex/link-shared-zshrc.sh)
  - `~/GitHub/scripts/setup/codex/link-shared-zshrc.sh --apply`
  - [`link-shared-zprofile.sh`](/Users/dobby/GitHub/scripts/setup/codex/link-shared-zprofile.sh)
  - `~/GitHub/scripts/setup/codex/link-shared-zprofile.sh --apply`

## Healthy State Checklist

- `~/.codex` is runtime-only:
  - `git -C ~/.codex rev-parse --git-dir` should fail
- `~/.zshrc` points at the shared tracked shell file:
  - `readlink ~/.zshrc`
  - expected target: `~/GitHub/scripts/setup/codex/zshrc.shared`
- `~/.zprofile` points at the shared tracked login-shell file:
  - `readlink ~/.zprofile`
  - expected target: `~/GitHub/scripts/setup/codex/zprofile.shared`
- Ghostty points at the canonical Codex startup wrapper:
  - `initial-command = direct:$HOME/.agents/codex/scripts/ghostty-codex-then-shell.sh`
- `~/.codex/config.toml` does not use Codex `notify`; global hook automation is rendered into `~/.codex/hooks.json`, and repo-assigned hooks are rendered into managed repo `.codex/hooks.json` from `hooks/registry.json`.
- The global `Stop` hook owns the managed-repo git conveyor:
  - stages all changes with `git add -A`
  - commits so each repo's own `scripts/check-fast.sh` checks decide whether the change is acceptable
  - relies on managed repo local `core.hooksPath` pointing at `~/.agents/hooks/git`
  - returns hook continuation JSON with commit/check failures so the current agent can fix them
  - tracked branches use an optimistic `commit -> push` path and only run `git pull --rebase` when push reports that the remote is ahead
  - brand-new branches without upstream tracking use an initial `git push -u <remote> HEAD`, so the hook can publish the branch before future tracked-branch pulls
  - logs phase timing to `~/.local/state/agents-control-plane/log/hooks-stop.log`
- `~/.codex/config.toml` contains exact trusted repo entries for local repos such as `focus`
- `~/.codex/config.toml` enables Codex hooks through `[features].hooks = true`
- `~/.codex/config.toml` contains `[hooks.state]` trust hashes for managed hooks rendered by this control plane, so global and repo-local lifecycle hooks do not need repeated `/hooks` review on every machine bootstrap.
- `~/.codex/config.toml` explicitly preserves enabled native Codex plugins such as `computer-use@openai-bundled`, points `openai-bundled` at the marketplace inside `Codex.app`, and disables bundled Codex skills classified as `disabled` in [`bundled-skills-policy.json`](/Users/dobby/.agents/codex/config/bundled-skills-policy.json)
- `~/.codex/hooks.json` is rendered from `hooks/registry.json` for global Codex hooks. The managed `Stop` hook renders there; repo-specific lifecycle hooks such as `SessionStart`, `UserPromptSubmit`, and `SessionEnd` render into repo `.codex/hooks.json`.
- `com.<user>.codex-thread-finalizer` is loaded as a LaunchAgent and runs [`finalize-stale-codex-threads.py`](/Users/dobby/.agents/codex/scripts/finalize-stale-codex-threads.py) every 6 hours against managed repo paths from [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json).
- `~/.codex/config.toml` contains no Git conflict markers
- `~/.codex/vendor_imports/skills` is a valid Git checkout:
  - `git -C ~/.codex/vendor_imports/skills rev-parse --show-toplevel`

## Main Scripts And Jobs

- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - applies the canonical Codex config template into the live global config
  - keeps Apps/connectors globally disabled through the managed `features.apps = false` baseline
  - renders global-scope native Codex plugin enable/disable state from [`plugins/registry.json`](/Users/dobby/.agents/plugins/registry.json)
  - points the `openai-bundled` marketplace at `Codex.app` directly and seeds `~/.codex/plugins/cache` only for bundled plugins enabled by the registry
  - disables selected bundled Codex skills in `~/.codex/config.toml` from [`bundled-skills-policy.json`](/Users/dobby/.agents/codex/config/bundled-skills-policy.json) when the control plane should prefer managed skill copies or avoid duplicate runtime surfaces
  - rewrites machine-specific system-skill paths for the current `$HOME`
  - renders only global Codex lifecycle hooks from [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) into `~/.codex/hooks.json`
  - strips foreign-user project and system-skill entries before writing
  - prunes stale global `apps.*` and `plugins.*` sections that are no longer present in the canonical template or plugin registry, so old local connector/plugin state does not stick around
  - prunes stale global terminal `mcp_servers.*` sections that are no longer present in the canonical template
  - prunes stale managed agent declarations and runtime role files left by older control-plane versions
  - fails fast if the target config contains unresolved Git conflict markers
  - skips no-op rewrites
- [`sync-hook-trust-state.py`](/Users/dobby/.agents/codex/scripts/sync-hook-trust-state.py)
  - computes Codex's normalized hook trust hash for managed global and repo-local hooks
  - writes those hashes under `[hooks.state]` in `~/.codex/config.toml`
  - is intentionally scoped to hooks rendered from the shared control plane, not arbitrary repo hooks
- [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - scans repo roots from the canonical repo bootstrap registry (defaults to `~/GitHub`)
  - includes explicit extra managed repos such as `~/.agents`
  - writes exact `[projects."<path>"] trust_level = "trusted"` entries
  - skips no-op rewrites
- [`sync-repo-codex-configs.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - renders managed repo-local Codex files from the shared repo inventory plus shared MCP and hook registries
  - renders repo-scoped native Codex plugin assignments from [`plugins/registry.json`](/Users/dobby/.agents/plugins/registry.json)
  - supports `--check` to fail when rendered repo-local files differ from the current `.codex` files
  - writes `.codex/config.toml` for all managed repos
  - writes `.codex/hooks.json` for all managed repos with only the hooks assigned to that repo
  - prunes stale managed repo-local `.codex/agents/*.toml` files left by older control-plane versions
  - skips no-op rewrites instead of dirtying the git repos unnecessarily
  - keeps the repo list and repo-level MCP/model assignments in [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
  - resolves MCP preset definitions through [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json)
- [`sync-managed-git-hooks.sh`](/Users/dobby/.agents/scripts/sync-managed-git-hooks.sh)
  - applies local-only `core.hooksPath` for every managed repo in [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
  - points Git at [`hooks/git/pre-commit`](/Users/dobby/.agents/hooks/git/pre-commit)
  - does not edit repo worktree files and does not affect GitHub Actions
- [`check-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/check-codex-control-plane.sh)
  - validates canonical `global.config.toml`, `repo-bootstrap.json`, and `mcp/config/presets.json`
  - validates [`bundled-skills-policy.json`](/Users/dobby/.agents/codex/config/bundled-skills-policy.json) and fails if a local OpenAI-bundled Codex skill exists under `~/.codex/skills/.system` or `~/.codex/skills/codex-primary-runtime` without being classified as `allowed` or `disabled`
  - validates that the live global Codex config disables each skill classified as `disabled`
  - validates [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json), rendered global `~/.codex/hooks.json`, and rendered repo-local `.codex/hooks.json` files when hooks are enabled
  - fails if managed agent declarations reappear in canonical or generated Codex config
  - runs `sync-repo-codex-configs.sh --check`, so stale or hand-edited repo-local `.codex/config.toml`, `.codex/hooks.json`, and older managed `.codex/agents/*.toml` files fail validation
- [`sync-repo-bootstrap-registry.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-bootstrap-registry.sh)
  - validates [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
  - pulls MCP preset definitions from [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json)
  - validates repo MCP assignments against canonical standalone preset groups
- [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - runs config sync
  - runs trusted-project sync
  - runs repo-local Codex config sync
  - runs Ghostty config reconciliation
  - installs the stale-thread finalization LaunchAgent
  - runs control-plane validation at the end and fails if the rendered state is inconsistent
- [`finalize-stale-codex-threads.py`](/Users/dobby/.agents/codex/scripts/finalize-stale-codex-threads.py)
  - starts a short-lived Codex app-server JSONL client, uses `thread/list` for eligibility, then invokes [`finalize-codex-thread.py`](/Users/dobby/.agents/codex/scripts/finalize-codex-thread.py) for each stale thread
  - reads managed repo paths from [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json) unless `--repo` filters are supplied
  - finalizes only non-archived threads whose `updatedAt` is older than the configured threshold; default is 48 hours
  - does not try to detect what the Desktop app currently has loaded; the safety boundary is the last-activity cutoff
  - defaults to dry-run; use `--apply` for actual finalization
  - uses a machine-local lock under `~/.local/state/codex-control-plane/` so overlapping launchd runs do not race
- [`finalize-codex-thread.py`](/Users/dobby/.agents/codex/scripts/finalize-codex-thread.py)
  - takes only `--thread-id` as canonical thread identity
  - uses app-server `thread/read` to derive the thread `cwd`, resolves the repo root, runs optional repo policy at `scripts/hooks/finalize_codex_thread.py`, runs one same-thread finalization turn when the repo emits an instruction, then archives the source thread through `thread/archive`
  - for repos without `scripts/hooks/finalize_codex_thread.py`, finalization is archive-only
- [`prune-sidebar-projects.py`](/Users/dobby/.agents/codex/scripts/prune-sidebar-projects.py)
  - removes stale project roots from Codex Desktop sidebar state without deleting repo files or session files
  - reads Codex thread activity from app-server `thread/list` by default, so cleanup follows Codex's listable thread view rather than every Desktop workspace bookkeeping row
  - default activity logic keeps a project when it has a recently created thread, including archived threads, or a recently updated unarchived thread
  - supports `--activity-source sqlite` as a read-only diagnostic/fallback when the exact local state DB view is needed
  - uses app-server `thread/archive` for stale unarchived threads when `--apply` is used, so it does not write thread archive flags directly into SQLite
  - prunes local saved roots from `electron-saved-workspace-roots` and stale remote entries from `remote-projects`; matching `project-order` entries are removed at the same time
  - backs up `.codex-global-state.json` and `state_5.sqlite*` under `~/.local/state/codex-control-plane/sidebar-project-prune/backups/` before applying changes
  - defaults to dry-run and emits JSON by default; use `--plain` for compact operator inspection
- [`install-finalize-stale-codex-threads-launchagent.sh`](/Users/dobby/.agents/codex/scripts/install-finalize-stale-codex-threads-launchagent.sh)
  - renders `~/Library/LaunchAgents/com.<user>.codex-thread-finalizer.plist`
  - schedules [`finalize-stale-codex-threads.py`](/Users/dobby/.agents/codex/scripts/finalize-stale-codex-threads.py) every 6 hours by default
  - removes the legacy `com.<user>.codex-session-archiver` LaunchAgent if present during apply
  - writes logs under `~/.local/state/codex-control-plane/log/`
  - supports dry-run output before writing or loading launchd state
- [`install-sidebar-project-prune-launchagent.sh`](/Users/dobby/.agents/codex/scripts/install-sidebar-project-prune-launchagent.sh)
  - renders `~/Library/LaunchAgents/com.<user>.codex-sidebar-project-pruner.plist`
  - schedules [`prune-sidebar-projects.py`](/Users/dobby/.agents/codex/scripts/prune-sidebar-projects.py) at 01:00 daily by default
  - forwards `--quit-codex-app --reopen-codex-app` so the disk state is changed while Codex Desktop is not holding stale sidebar state in memory
  - writes logs under `~/.local/state/codex-control-plane/log/`
  - supports dry-run output before writing or loading launchd state
- [`auto-apply-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/auto-apply-codex-control-plane.sh)
  - checks whether `~/.agents/codex/` changed since the last successful reconcile on that machine
  - runs [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh) only when a new Codex control-plane revision needs to be applied
  - stores a machine-local reconcile stamp under `~/.local/state/codex-control-plane/`
  - remains available when you intentionally want a Codex-only reconcile outside the shared machine-facing wrapper
- [`configure-ghostty-cwd.sh`](/Users/dobby/.agents/codex/scripts/configure-ghostty-cwd.sh)
  - ensures Ghostty uses the Codex startup wrapper
  - ensures shell integration stays on
  - removes legacy Ghostty-owned picker keybinds so Keyboard Maestro can own the optional shortcuts cleanly
- [`open-ghostty-codex-picker-current.sh`](/Users/dobby/.agents/codex/scripts/open-ghostty-codex-picker-current.sh)
  - inputs `codex_jump` into the focused Ghostty terminal
  - is the tracked helper used by the optional manual Keyboard Maestro `Cmd+Shift+G` macro
- [`codex-shell.zsh`](/Users/dobby/.agents/codex/shell/codex-shell.zsh)
  - `codex_jump` sets the Ghostty tab/surface title to the selected repo basename before launching Codex
  - `codex_jump` also reports the selected cwd back to Ghostty immediately so regular new tabs and splits inherit the active repo instead of falling back to `~`
  - `codex_jump` ranks picker rows by a decaying active working-set score: each selection adds `1`, scores halve every 6 hours by default, and `CODEX_JUMP_SCORE_HALFLIFE_HOURS` can tune the half-life
  - records the active Ghostty/Codex working directory to `~/.local/state/codex-control-plane/ghostty-last-dir.txt` so cold Ghostty launches can resume there
- [`ghostty-codex-then-shell.sh`](/Users/dobby/.agents/codex/scripts/ghostty-codex-then-shell.sh)
  - reports the current cwd and repo basename title before the first-surface Codex launch so Ghostty new-window inheritance can reuse the active repo
  - restores the last recorded working directory on cold Ghostty launches when startup otherwise lands in `~`
- [`open-ghostty-codex-tab.sh`](/Users/dobby/.agents/codex/scripts/open-ghostty-codex-tab.sh)
  - opens a new Ghostty tab with a custom surface configuration and immediately runs `codex`
  - is the tracked helper used by the optional manual Keyboard Maestro `Cmd+Opt+T` macro
- [`open-ghostty-codex-split.sh`](/Users/dobby/.agents/codex/scripts/open-ghostty-codex-split.sh)
  - opens a Ghostty split with a custom surface configuration and immediately runs `codex`
  - is the tracked helper used by the optional manual Keyboard Maestro `Cmd+Opt+D` macro
- [`open-ghostty-codex-picker-tab.sh`](/Users/dobby/.agents/codex/scripts/open-ghostty-codex-picker-tab.sh)
  - opens a new Ghostty tab with a custom surface configuration and immediately runs `codex_jump`
  - is the one tracked helper used by both the Stadia controller `Share` action and the optional manual Keyboard Maestro `Cmd+Shift+T` macro
- [`open-ghostty-codex-picker-split.sh`](/Users/dobby/.agents/codex/scripts/open-ghostty-codex-picker-split.sh)
  - opens a Ghostty split with a custom surface configuration and immediately runs `codex_jump` in the new split
  - is the tracked helper used by the Stadia controller `leftThumbstickButton` split-picker action
- [`open-ghostty-plain-shell-split.sh`](/Users/dobby/.agents/codex/scripts/open-ghostty-plain-shell-split.sh)
  - opens a Ghostty split with `CODEX_DISABLE_AUTOSTART=1` so the new pane stays a plain shell in the inherited cwd even if autostart is re-enabled for a session
  - remains available as a helper when you explicitly need a plain-shell split override beyond Ghostty's default `Cmd+D`

## Shared Registry Fields

- [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json) currently controls these per-repo fields:
  - `mcp_presets`
  - `model`
  - `model_auto_compact_token_limit`
  - `model_reasoning_effort`
  - `plan_mode_reasoning_effort`
  - `model_verbosity`
  - `personality`
  - `model_instructions_file`
  - `developer_instructions`
  - `project_root_markers`
  - `features`
  - `service_tier`
- Shared MCP preset definitions live separately in [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json).
- Shared lifecycle hook definitions live separately in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json).
- Native Codex plugin scope and state lives separately in [`plugins/registry.json`](/Users/dobby/.agents/plugins/registry.json).
- The global defaults block supplies fallback values for repos that do not override them.

## Automatic Cross-Machine Apply

- Launchd still lives in [`~/GitHub/scripts/sync/git-auto-sync.sh`](/Users/dobby/GitHub/scripts/sync/git-auto-sync.sh), because scheduler ownership is part of the generic machine-ops repo.
- Machine-facing multi-surface apply now lives in [`auto-apply-agent-control-planes.sh`](/Users/dobby/.agents/scripts/auto-apply-agent-control-planes.sh), which calls the Codex and shared repo-local entrypoints as needed after `~/.agents` sync.
- When shared skill inputs change, that wrapper also reruns the Codex bootstrap so machine-side dependencies for managed skills such as `pdf` stay converged.
- That same wrapper validates the plugin registry and reapplies Codex config when plugin state changes.
- When `hooks/registry.json` or `codex/config/repo-bootstrap.json` changes, that wrapper syncs global Codex hooks and repo-local Codex hooks in managed repos.
- Codex-specific post-sync apply logic still lives in [`auto-apply-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/auto-apply-codex-control-plane.sh) as an optional lower-level Codex-only reconcile helper.
- Practical flow:
  1. one machine pushes a change in `~/.agents`
  2. the other machine pulls it on the next git auto-sync cycle
  3. `git-auto-sync.sh` calls `auto-apply-agent-control-planes.sh`
  4. that script runs the required shared skills, plugin, Git hook, and Codex apply steps based on what changed
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
- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh) now rewrites local system-skill paths and strips foreign-user project entries before applying

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
  - Adi MacBook via SSH alias `adithyans-macbook-pro` under `/Users/adi`
    - this alias is managed by `~/GitHub/scripts/setup/reconcile-ssh-machine-hosts.sh`
    - it reaches the MacBook through Tailscale with `ProxyCommand tailscale nc %h %p`
    - older references to `macbook-wan` are stale and should not be used as current setup guidance
- The control plane is designed to be home-relative at apply time, not by committing one machine's absolute paths into canonical templates.
