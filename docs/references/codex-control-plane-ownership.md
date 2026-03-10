# Codex Control Plane Ownership

This document is the exact ownership reference for the Codex control-plane migration.

Use [Codex Control Plane](/Users/dobby/.agents/docs/architecture/codex-control-plane.md) for the high-level shape and this file for concrete keep / move / generate decisions.

## Ownership Rules

- `~/.agents` owns canonical, synced, durable Codex control-plane inputs.
- `~/GitHub/scripts` owns machine bootstrap entrypoints that delegate into `~/.agents`.
- `~/.codex` owns live runtime state and generated applied outputs.
- Repo-local `.codex/` owns project-specific Codex overrides.

## Keep / Move / Generate

### Keep in `~/.agents`

- Codex architecture docs and migration trackers
- Codex-specific managed scripts
- canonical config fragments and presets
- MCP preset definitions and ownership docs
- any launchd or apply logic that is specifically about Codex behavior across machines

### Keep in `~/GitHub/scripts`

- fresh-machine bootstrap entrypoints
- generic setup flows that call the Codex control plane
- thin wrappers that apply managed Codex state onto a machine

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
- [.codex/config.toml](/Users/dobby/.codex/.codex/config.toml): project-scoped override for the `~/.codex` repo itself; reassess after migration depending on whether `~/.codex` remains git-tracked.
- live `config.toml` now points at the canonical notify source in [notify.py](/Users/dobby/.agents/codex/scripts/notify.py).
- [AGENTS.md](/Users/dobby/.codex/AGENTS.md) and [docs/AGENTS.md](/Users/dobby/.codex/docs/AGENTS.md): keep only if `~/.codex` remains a meaningful repo; otherwise they can move or disappear with the repo layer.

### `~/GitHub/scripts`

- [setup/codex/AGENTS.md](/Users/dobby/GitHub/scripts/setup/codex/AGENTS.md): currently describes portable Codex bootstrap ownership; it will need to be updated once canonical ownership moves into `~/.agents`.
- [setup/sync-codex-config.sh](/Users/dobby/GitHub/scripts/setup/sync-codex-config.sh): should remain an entrypoint, but may delegate to canonical sources in `~/.agents`.
- [setup/bootstrap-machine.sh](/Users/dobby/GitHub/scripts/setup/bootstrap-machine.sh): should continue calling the apply flow after the ownership move.

### `~/.agents`

- [AGENTS.md](/Users/dobby/.agents/AGENTS.md): likely needs a small update once `.agents` formally owns the Codex control plane.
- [docs/architecture/codex-control-plane.md](/Users/dobby/.agents/docs/architecture/codex-control-plane.md): canonical high-level design.
- [docs/projects/codex-control-plane/tasks.md](/Users/dobby/.agents/docs/projects/codex-control-plane/tasks.md): active project tracker for the migration.

## Migration Intent

Short term:

- add the canonical Codex control-plane folder under `~/.agents`
- move the first durable Codex-managed assets there
- rewire `~/GitHub/scripts` to delegate
- keep mixed shell-dotfile assets in `~/GitHub/scripts/setup/codex/` until they are split cleanly from general shell concerns

Later:

- decide whether `~/.codex` should keep its git repo role
- remove remaining duplicated Codex policy from `~/GitHub/scripts`
- reduce `~/.codex` to a cleaner applied runtime home
