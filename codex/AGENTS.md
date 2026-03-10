# Codex Control Plane

Canonical personal Codex control-plane assets live here.

## Purpose

- Keep synced, durable Codex configuration under `~/.agents`.
- Keep `~/GitHub/scripts` as the machine bootstrap/apply shell, not the long-term owner of Codex policy.
- Keep `~/.codex` as the applied runtime home.

## Layout

- `config/`: canonical Codex config fragments and templates.
- `scripts/`: canonical Codex-specific automation scripts.

## Rules

- Do not store auth, session history, caches, logs, runtime databases, or secrets here.
- If a script must run from `~/.codex` or another runtime path, keep the canonical source here and sync or point to it from the runtime config.
- Prefer repo-local `.codex/config.toml` for project-specific MCP/tool behavior instead of putting repo policy here.
- Keep mixed shell-dotfile concerns out of this folder until they are cleanly split from Codex-only behavior.

## Current Scope

- `scripts/sync-config.sh` is the canonical sync/apply entrypoint for machine Codex config.
- `config/global.config.toml` and `config/xcode.config.toml` are the canonical managed baselines.
- `scripts/notify.py` is the canonical notify automation source.
