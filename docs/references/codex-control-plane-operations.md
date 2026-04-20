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
  - shared zprofile in [`setup/codex/zprofile.shared`](/Users/dobby/GitHub/scripts/setup/codex/zprofile.shared)
  - machine bootstrap entrypoint in [`setup/bootstrap-machine.sh`](/Users/dobby/GitHub/scripts/setup/bootstrap-machine.sh)
- `~/.codex`
  - live runtime home only
  - applied `config.toml`, global `hooks.json`, auth, sessions, logs, caches, sqlite, shell snapshots
  - Codex-managed vendor imports in `vendor_imports/`, including the nested Git checkout at `vendor_imports/skills`
  - should not be a git repo
- `~/.local/state/codex-control-plane`
  - machine-local reconcile stamps and quarantine state

## Canonical Commands

- Apply the shared machine-facing agent bootstrap batch:
  - [`bootstrap-machine-agent-control-planes.sh`](/Users/dobby/.agents/scripts/bootstrap-machine-agent-control-planes.sh)
  - `~/.agents/scripts/bootstrap-machine-agent-control-planes.sh --apply`
  - this syncs managed skill links, plugin-derived skills and MCP state, plus the Codex and Claude runtime control planes from one stable root entrypoint
- Auto-apply the shared agent control plane after `~/.agents` sync when runtime-relevant files changed:
  - [`auto-apply-agent-control-planes.sh`](/Users/dobby/.agents/scripts/auto-apply-agent-control-planes.sh)
  - `~/.agents/scripts/auto-apply-agent-control-planes.sh --apply`
  - this is the machine-facing post-sync entrypoint that external bootstrap repos should call
- Validate shared skills, plugins, plus Codex and Claude rendered runtime state:
  - [`check-agent-control-planes.sh`](/Users/dobby/.agents/scripts/check-agent-control-planes.sh)
  - `~/.agents/scripts/check-agent-control-planes.sh`
- Sync managed plugins and regenerate the Obsidian registry views:
  - [`sync-plugins-registry.sh`](/Users/dobby/.agents/scripts/sync-plugins-registry.sh)
  - `~/.agents/scripts/sync-plugins-registry.sh --apply`
  - this also refreshes plugin-derived skills and MCP state in the canonical registries
- Refresh managed external plugins from upstream:
  - [`refresh-external-plugins.sh`](/Users/dobby/.agents/scripts/refresh-external-plugins.sh)
  - `~/.agents/scripts/refresh-external-plugins.sh --apply`
- Bootstrap one managed plugin into the canonical registry:
  - [`bootstrap-plugin.sh`](/Users/dobby/.agents/scripts/bootstrap-plugin.sh)
  - `~/.agents/scripts/bootstrap-plugin.sh build-ios-apps --repo codexclaw --apply`
  - this writes the registry entry, refreshes upstream plugin source, regenerates plugin-derived skills and MCP state, and reapplies the shared control planes
- Apply the full Codex bootstrap batch:
  - [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - `~/.agents/codex/scripts/bootstrap-machine-codex.sh --apply`
  - this applies the Codex control-plane outputs only; shared shell links still come from `~/GitHub/scripts/setup/codex/`
- Auto-apply the Codex control plane after `~/.agents` sync when `codex/` changed:
  - [`auto-apply-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/auto-apply-codex-control-plane.sh)
  - `~/.agents/codex/scripts/auto-apply-codex-control-plane.sh --apply`
  - use this for targeted Codex-only troubleshooting or component-scoped automation, not as the machine-facing shared reconcile entrypoint
- Apply only the managed Codex config:
  - [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - `~/.agents/codex/scripts/sync-config.sh --apply`
  - this syncs the managed global config, global `hooks.json`, and only the agent-role files actually referenced by the managed global/Xcode configs into the live runtime `agents/` folders
- Validate canonical and rendered Codex control-plane state:
  - [`check-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/check-codex-control-plane.sh)
  - `~/.agents/codex/scripts/check-codex-control-plane.sh`
- Sync exact trusted repo roots into terminal + Xcode Codex config:
  - [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - `~/.agents/codex/scripts/sync-trusted-projects.sh --apply`
- Sync repo-local `.codex/config.toml` files from the canonical registry:
  - [`sync-repo-codex-configs.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - `~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply`
- Regenerate the Obsidian Base artifacts for the repo bootstrap registry:
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
- `~/.codex/config.toml` does not use Codex `notify`; post-turn automation is rendered into `~/.codex/hooks.json` from `hooks/registry.json`.
- The shared `Stop` hook owns the machine-wide git conveyor:
  - stages all changes with `git add -A`
  - commits so each repo's own `scripts/check-fast.sh` checks decide whether the change is acceptable
  - relies on managed repo local `core.hooksPath` pointing at `~/.agents/hooks/git`
  - returns hook continuation JSON with commit/check failures so the current agent can fix them
  - tracked branches use the normal `commit -> pull --rebase -> push` path
  - brand-new branches without upstream tracking use an initial `git push -u <remote> HEAD`, so the hook can publish the branch before future tracked-branch pulls
- `~/.codex/config.toml` and Xcode Codex config contain exact trusted repo entries for local repos such as `focus`
- `~/.codex/config.toml` enables Codex hooks through `[features].codex_hooks = true`
- `~/.codex/hooks.json` is rendered from `hooks/registry.json`
- `~/.codex/config.toml` contains no Git conflict markers
- `~/.codex/vendor_imports/skills` is a valid Git checkout:
  - `git -C ~/.codex/vendor_imports/skills rev-parse --show-toplevel`

## Main Scripts And Jobs

- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - applies canonical Codex config templates into live terminal + Xcode config
  - derives global managed agent declarations from [`agents/registry.json`](/Users/dobby/.agents/agents/registry.json)
  - syncs only the role config files referenced by the managed global + Xcode configs into the live runtime `agents/` directories
  - keeps the current role setup explicit: built-in `explorer` for local repo/runtime exploration, managed `external_researcher` for information outside the local repo/runtime
  - leaves repo-scoped custom roles to the repo bootstrap path instead of enabling them globally by default
  - keeps Apps/connectors globally disabled through the managed `features.apps = false` baseline and explicit static `plugins.*.enabled = false` entries in the canonical template where desired
  - disables selected built-in system skills in `~/.codex/config.toml` when the control plane should prefer managed skill copies instead, including currently `imagegen`, `openai-docs`, `skill-creator`, and `skill-installer`
  - rewrites machine-specific system-skill paths for the current `$HOME`
  - renders global Codex lifecycle hooks from [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) into `~/.codex/hooks.json`
  - strips foreign-user project and system-skill entries before writing
  - prunes stale global `apps.*` and `plugins.*` sections that are no longer present in the canonical template, so old local connector/plugin state does not stick around
  - prunes stale global terminal `mcp_servers.*` sections that are no longer present in the canonical template
  - validates role-file invariants before install, including non-empty `name` + `description`
  - fails fast if the target config contains unresolved Git conflict markers
  - skips no-op rewrites
- [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - scans repo roots from the canonical repo bootstrap registry (defaults to `~/GitHub`)
  - includes explicit extra managed repos such as `~/.agents`
  - writes exact `[projects."<path>"] trust_level = "trusted"` entries
  - skips no-op rewrites
- [`sync-repo-codex-configs.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - renders managed repo-local Codex files from the shared repo inventory plus the shared agent registry
  - supports `--check` to fail when rendered repo-local files differ from the current `.codex` files
  - writes `.codex/config.toml` for all managed repos
  - writes repo-local `.codex/agents/*.toml` files for any repo-scoped Codex agents assigned in [`agents/registry.json`](/Users/dobby/.agents/agents/registry.json)
  - copies canonical role behavior from [`codex/config/agents/*.toml`](/Users/dobby/.agents/codex/config/agents) into those repo-local agent files
  - validates repo-scoped agent role files before writing them into managed repos
  - skips no-op rewrites instead of dirtying the git repos unnecessarily
  - keeps the repo list and repo-level MCP/model assignments in [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
  - keeps shared agent scope and runtime metadata in [`agents/registry.json`](/Users/dobby/.agents/agents/registry.json)
  - resolves MCP preset definitions through [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json), including plugin-derived presets and repo assignments
- [`sync-managed-git-hooks.sh`](/Users/dobby/.agents/scripts/sync-managed-git-hooks.sh)
  - applies local-only `core.hooksPath` for every managed repo in [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
  - points Git at [`hooks/git/pre-commit`](/Users/dobby/.agents/hooks/git/pre-commit)
  - does not edit repo worktree files and does not affect GitHub Actions
- [`check-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/check-codex-control-plane.sh)
  - validates canonical `global.config.toml`, `xcode.config.toml`, `repo-bootstrap.json`, `agents/registry.json`, and `mcp/config/presets.json`
  - validates [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) and rendered global `~/.codex/hooks.json` when hooks are enabled
  - validates canonical role TOMLs and rendered runtime role TOMLs
  - catches missing or malformed `name` / `description` in role files
  - catches runtime `agents/` directories containing unreferenced role files
  - validates generated repo-local `.codex/config.toml` agent declarations for managed repos present on the machine
  - runs `sync-repo-codex-configs.sh --check`, so stale or hand-edited repo-local `.codex/config.toml` and `.codex/agents/*.toml` files fail validation
- [`sync-repo-bootstrap-registry.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-bootstrap-registry.sh)
  - regenerates the Obsidian Base artifacts from [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
  - reads shared agent exposure from [`agents/registry.json`](/Users/dobby/.agents/agents/registry.json)
  - pulls MCP preset definitions from [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json)
  - enriches the per-repo view with effective skills from [`skills/registry.json`](/Users/dobby/.agents/skills/registry.json), including plugin-derived skills
  - enriches the per-repo view with repo MCP assignments from both canonical and plugin-derived preset groups
  - now also exposes effective agents per repo:
    - `global_agents`
    - `custom_agents`
    - `agents`
  - and generates a role-centric agent registry with both scope and capability data
  - updates the user-facing registry views under [`docs/references/registry/`](/Users/dobby/.agents/docs/references/registry)
  - includes [`repo-bootstrap.base`](/Users/dobby/.agents/docs/references/registry/repo-bootstrap.base), [`repo-bootstrap-items/`](/Users/dobby/.agents/docs/references/registry/repo-bootstrap-items), [`mcp-registry.base`](/Users/dobby/.agents/docs/references/registry/mcp-registry.base), [`mcp-registry-items/`](/Users/dobby/.agents/docs/references/registry/mcp-registry-items), [`agent-registry.base`](/Users/dobby/.agents/docs/references/registry/agent-registry.base), and [`agent-registry-items/`](/Users/dobby/.agents/docs/references/registry/agent-registry-items)
- [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - runs config sync
  - runs trusted-project sync
  - runs repo-local Codex config sync
  - runs Ghostty config reconciliation
  - runs control-plane validation at the end and fails if the rendered state is inconsistent
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
  - `model_reasoning_effort`
  - `plan_mode_reasoning_effort`
  - `model_verbosity`
  - `personality`
  - `model_instructions_file`
  - `developer_instructions`
  - `project_root_markers`
  - `features`
  - `service_tier`
- [`agents/registry.json`](/Users/dobby/.agents/agents/registry.json) controls shared agent exposure and runtime-specific metadata:
  - `agent`
  - `scope`
  - `repos`
  - `access_profile`
  - nested `codex`
  - nested `claude`
- Shared MCP preset definitions live separately in [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json).
- Shared lifecycle hook definitions live separately in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json).
- Shared plugin source extraction state lives separately in [`plugins/registry.json`](/Users/dobby/.agents/plugins/registry.json).
- Agent behavior itself stays in [`codex/config/agents/*.toml`](/Users/dobby/.agents/codex/config/agents), including MCP posture, tool disables, feature disables, and sandbox level.
- The global defaults block supplies fallback values for repos that do not override them.

## Automatic Cross-Machine Apply

- Launchd still lives in [`~/GitHub/scripts/sync/git-auto-sync.sh`](/Users/dobby/GitHub/scripts/sync/git-auto-sync.sh), because scheduler ownership is part of the generic machine-ops repo.
- Machine-facing multi-surface apply now lives in [`auto-apply-agent-control-planes.sh`](/Users/dobby/.agents/scripts/auto-apply-agent-control-planes.sh), which calls the Codex and Claude entrypoints as needed after `~/.agents` sync.
- When shared skill inputs change, that wrapper also reruns the Codex bootstrap so machine-side dependencies for managed skills such as `pdf` stay converged.
- That same wrapper now also runs the managed external plugin refresh once per day, then re-syncs plugin-derived skills and MCP state.
- When `agents/registry.json` changes, that wrapper reruns both the Codex and Claude bootstraps so global and repo-local agent surfaces stay converged.
- Codex-specific post-sync apply logic still lives in [`auto-apply-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/auto-apply-codex-control-plane.sh) as an optional lower-level Codex-only reconcile helper.
- Practical flow:
  1. one machine pushes a change in `~/.agents`
  2. the other machine pulls it on the next git auto-sync cycle
  3. `git-auto-sync.sh` calls `auto-apply-agent-control-planes.sh`
  4. that script runs the required shared skills, Codex, and Claude apply steps based on what changed
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
  - MacBook via SSH alias `macbook-wan` under `/Users/adi`
- The control plane is designed to be home-relative at apply time, not by committing one machine's absolute paths into canonical templates.
