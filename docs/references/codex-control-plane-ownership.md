# Codex Control Plane Ownership

This document is the exact ownership reference for the Codex control-plane migration.

Use [Codex Control Plane](/Users/dobby/.agents/docs/architecture/codex-control-plane.md) for the high-level shape and this file for concrete keep / move / generate decisions.

## Ownership Rules

- `~/.agents` owns canonical, synced, durable Codex control-plane inputs.
- `~/GitHub/scripts` owns generic machine bootstrap entrypoints and shared shell glue that are not Codex-owned.
- `~/.codex` owns live runtime state and generated applied outputs.
- Repo-local `.codex/` owns project-specific Codex overrides.

## Keep / Move / Generate

### Keep in `~/.agents`

- Codex architecture docs and migration trackers
- Codex-specific managed scripts
- canonical config fragments and presets
- MCP preset definitions and ownership docs
- any launchd or apply logic that is specifically about Codex behavior across machines
- the Codex-specific post-sync reconcile logic that decides whether a new `~/.agents/codex/` revision must be applied on a machine

### Keep in `~/GitHub/scripts`

- fresh-machine bootstrap entrypoints
- generic setup flows that may call the Codex control plane
- generic shared shell files that source Codex fragments from `~/.agents`
- generic launchd/scheduler entrypoints such as git auto-sync that may invoke Codex-owned reconcile scripts

### Keep in `~/.codex`

- `auth.json`
- `history.jsonl`
- `sessions/`
- `log/`
- `sqlite/`
- `state_*.sqlite`
- `shell_snapshots/`
- caches and temp files
- live `config.toml`
- runtime-installed skills and generated runtime artifacts
- runtime migration markers and indexes such as `.personality_migration`, `session_index.jsonl`, and runtime SQLite files
- Codex-managed vendor imports such as `vendor_imports/skills`, which is a nested Git checkout used by Codex App for recommended skills

### Generate or Sync Into `~/.codex`

- managed `config.toml` sections sourced from canonical files in `~/.agents`
- runtime-facing script entrypoints that Codex invokes directly
- any generated wrappers needed for notify or apply flows

### Keep Repo-Local

- project `.codex/config.toml`
- project-specific MCP enablement
- repo-local tool or app toggles
- repo-local trust and behavior overrides when they differ from machine defaults

## Current Notable Files

### `~/.codex`

- [config.toml](/Users/dobby/.codex/config.toml): live machine config; target is generated/applied, not hand-owned as the canonical source.
- live `config.toml` now points at the canonical notify source in [notify.py](/Users/dobby/.agents/codex/scripts/notify.py).
- `~/.codex` is now runtime-only; repo-only files such as `.git`, `.gitignore`, nested `.codex/config.toml`, and repo-router docs can be removed.
- [vendor_imports/skills](/Users/dobby/.codex/vendor_imports/skills): runtime-managed nested Git checkout from `openai/skills`; do not delete or flatten it during runtime cleanup.

### `~/GitHub/scripts`

- [setup/bootstrap-machine.sh](/Users/dobby/GitHub/scripts/setup/bootstrap-machine.sh): generic machine bootstrap entrypoint that may invoke the Codex control plane.
- [setup/codex/AGENTS.md](/Users/dobby/GitHub/scripts/setup/codex/AGENTS.md): now describes only the generic shared zshrc layer that remains here.
- [setup/codex/zshrc.shared](/Users/dobby/GitHub/scripts/setup/codex/zshrc.shared): now acts as generic shared shell bootstrap and sources the Codex shell fragment from `~/.agents`.

### `~/.agents`

 - [AGENTS.md](/Users/dobby/.agents/AGENTS.md): machine-local guidance for this repo; now includes the canonical Codex control-plane commands.
- [docs/architecture/codex-control-plane.md](/Users/dobby/.agents/docs/architecture/codex-control-plane.md): canonical high-level design.
- [docs/projects/archive/codex-control-plane/tasks.md](/Users/dobby/.agents/docs/projects/archive/codex-control-plane/tasks.md): archived project tracker for the completed migration.
- [codex/scripts/bootstrap-machine-codex.sh](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh): canonical Codex-specific machine bootstrap entrypoint.
- [codex/scripts/auto-apply-codex-control-plane.sh](/Users/adi/.agents/codex/scripts/auto-apply-codex-control-plane.sh): canonical Codex-specific post-sync reconcile entrypoint used for automatic cross-machine apply.
- [codex/scripts/sync-trusted-projects.sh](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh): canonical trusted-repo sync for terminal + Xcode Codex configs.
- [codex/scripts/sync-repo-codex-configs.sh](/Users/adi/.agents/codex/scripts/sync-repo-codex-configs.sh): canonical repo-local Codex config sync for managed repos.
- [codex/config/repo-bootstrap.json](/Users/adi/.agents/codex/config/repo-bootstrap.json): canonical repo bootstrap registry for managed repos plus MCP/model overrides.
- [codex/scripts/install-sudoers-codex-ops.sh](/Users/dobby/.agents/codex/scripts/install-sudoers-codex-ops.sh): canonical Codex sudoers installer.

## Migration Intent

Short term:

- add the canonical Codex control-plane folder under `~/.agents`
- move the first durable Codex-managed assets there
- move remaining Codex-specific setup wrappers and helpers out of `~/GitHub/scripts`
- keep only generic shared shell bootstrap in `~/GitHub/scripts/setup/codex/` and source Codex-specific shell behavior from `~/.agents`

Later:

- remove remaining duplicated Codex policy from `~/GitHub/scripts`
- reduce `~/.codex` to a cleaner applied runtime home
