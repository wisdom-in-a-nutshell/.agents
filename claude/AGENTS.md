# Claude Control Plane

Canonical personal Claude control-plane assets live here.

## Purpose

- Keep synced, durable Claude configuration under `~/.agents`.
- Keep `~/.claude` as the applied runtime home.
- Mirror the current Codex control-plane discipline where that improves reproducibility without forcing false parity.

## Layout

- `config/`: canonical Claude config fragments and templates.
  - `config/global.claude.md`: canonical machine-wide guidance source for `~/.claude/CLAUDE.md`.
  - `config/settings.json`: canonical machine-wide settings source for `~/.claude/settings.json`.
  - `config/bootstrap.json`: Claude-only bootstrap defaults and per-repo overrides.
- `scripts/`: canonical Claude-specific automation scripts.

## Rules

- Do not store auth, session history, caches, runtime databases, or secrets here.
- Keep durable Claude provider selection such as AWS Bedrock model env in `config/settings.json`; do not hand-edit `~/.claude/settings.json`.
- Prefer project `AGENTS.md` as the shared repo instruction source; generic Claude compatibility should come from a tiny `CLAUDE.md` that imports `@AGENTS.md`.
- Keep the first-pass Claude bootstrap local-first and generic; treat repo-specific prompt overrides such as `adi` `soul.md` as explicit follow-up work.
- Keep machine-local runtime state under `~/.claude/`, not in this repo.
- Treat `codex/config/repo-bootstrap.json` as the shared repo inventory and repo-assignment registry.
- Treat `mcp/config/presets.json` as the shared MCP registry for both Codex and Claude.
