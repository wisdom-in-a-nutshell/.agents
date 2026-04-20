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
  - `config/agents/*.md`: canonical Claude subagent prompt bodies rendered into `~/.claude/agents/` and repo `.claude/agents/`.
- `scripts/`: canonical Claude-specific automation scripts.

## Current Scope

- `../scripts/bootstrap-machine-agent-control-planes.sh` is the canonical machine-facing bootstrap batch for shared skills plus Codex and Claude.
- `../scripts/auto-apply-agent-control-planes.sh` is the canonical machine-facing post-sync reconcile entrypoint used by external bootstrap repos such as `~/GitHub/scripts`.
- `../scripts/check-agent-control-planes.sh` is the canonical shared validation entrypoint for skills plus Codex and Claude.
- `scripts/bootstrap-machine-claude.sh` is the canonical Claude-specific bootstrap batch used by the shared root wrappers.
- `scripts/check-claude-control-plane.sh` is the canonical Claude control-plane validation entrypoint.
- `scripts/sync-subagents.sh` is the canonical Claude subagent materialization entrypoint for `~/.claude/agents/` and repo `.claude/agents/`.
- `scripts/sync-skills.sh` is the canonical Claude skill materialization entrypoint for `~/.claude/skills/` and repo `.claude/skills/`.

## Rules

- Do not store auth, session history, caches, runtime databases, or secrets here.
- Keep durable Claude machine defaults in `config/settings.json`; use explicit shell wrappers for provider-specific opt-ins such as AWS Bedrock instead of forcing every machine onto one provider.
- Prefer project `AGENTS.md` as the shared repo instruction source; generic Claude compatibility should come from a tiny `CLAUDE.md` that imports `@AGENTS.md`.
- Keep the first-pass Claude bootstrap local-first and generic; treat repo-specific prompt overrides such as `adi` `soul.md` as explicit follow-up work.
- Keep machine-local runtime state under `~/.claude/`, not in this repo.
- Treat `codex/config/repo-bootstrap.json` as the shared repo inventory and repo-assignment registry.
- Treat `../agents/registry.json` as the shared agent exposure registry for Codex and Claude.
- Treat `mcp/config/presets.json` as the shared MCP registry for both Codex and Claude.
- Treat `config/bootstrap.json` as Claude-only settings and repo override input, not as the Claude subagent registry.

## References

- `../docs/architecture/claude-control-plane.md`: high-level system shape.
- `../docs/references/claude-control-plane-operations.md`: exact commands, runtime targets, and generated repo-local outputs.
