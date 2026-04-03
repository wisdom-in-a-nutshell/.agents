# Claude Control Plane Operations

Use this page for the exact operator-facing facts of the local Claude control plane.

Use [Claude Control Plane](/Users/adi/.agents/docs/architecture/claude-control-plane.md) for the high-level shape.

## Canonical Inputs

- `claude/config/global.claude.md`
  - canonical source for `~/.claude/CLAUDE.md`
- `claude/config/settings.json`
  - canonical source for `~/.claude/settings.json`
- `claude/config/bootstrap.json`
  - Claude-only bootstrap defaults and repo-specific overrides
- `codex/config/repo-bootstrap.json`
  - shared repo inventory plus per-repo assignment registry
- `mcp/config/presets.json`
  - shared MCP preset definitions and machine-wide global MCP defaults

## Runtime Targets

- `~/.claude/CLAUDE.md`
  - global guidance file
- `~/.claude/settings.json`
  - permissive user/global defaults
- `~/.claude.json`
  - user runtime state and global MCP store
- repo `CLAUDE.md`
  - usually a tiny file containing only `@AGENTS.md`
- repo `.claude/settings.json`
  - project settings
- repo `.mcp.json`
  - project MCP
- repo `.claude/skills/`
  - project skills
- nested repo `CLAUDE.md`
  - tiny file containing only `@AGENTS.md` wherever nested `AGENTS.md` exists

## First-Pass Commands

The Claude control plane is intended to follow the same sync/check pattern as Codex, with scripts living under `claude/scripts/`:

- `sync-global-claude-md.sh`
  - link `~/.claude/CLAUDE.md` to `claude/config/global.claude.md`
- `sync-settings.sh`
  - install the permissive global `settings.json` into `~/.claude/settings.json`
- `sync-global-mcp.sh`
  - merge global MCP entries from `mcp/config/presets.json` into `~/.claude.json`
- `sync-skills.sh`
  - materialize global and project Claude skills from `skills/registry.json`
- `sync-repo-claude-configs.sh`
  - render root and nested `CLAUDE.md` compatibility files, `.claude/settings.json`, and `.mcp.json` from the shared repo registry plus Claude bootstrap overlay
- `bootstrap-machine-claude.sh`
  - run the full Claude apply batch
- `check-claude-control-plane.sh`
  - validate canonical inputs and rendered outputs

## Supported Manual Rules

- `CLAUDE.md` should contain only `@AGENTS.md` for the generic case.
- Nested `AGENTS.md` files should also get sibling `CLAUDE.md` files containing only `@AGENTS.md`.
- `AGENTS.md` remains the shared repo instruction source.
- `skipDangerousModePermissionPrompt` belongs in user/global Claude settings, not project settings.
- `enableAllProjectMcpServers` is part of the permissive global baseline.
- `sandbox.enabled = false` is the closest local no-sandbox default.

## Current Global Settings Baseline

- `claude/config/settings.json` is the source of truth for `~/.claude/settings.json`.
- AWS Bedrock enablement is intentionally hard-coded in the canonical global settings, not patched manually into runtime state.
- The current global baseline pins:
  - `Sonnet 4.6 (Bedrock)` -> `us.anthropic.claude-sonnet-4-6`
  - `Opus 4.6 (Bedrock)` -> `us.anthropic.claude-opus-4-6-v1`
  - `Haiku 4.5 (Bedrock)` -> `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `CLAUDE_CODE_USE_BEDROCK=1` and `AWS_REGION=us-east-1` are part of that managed baseline.

## Scope Rules

- Global Claude guidance lives in `~/.claude/CLAUDE.md`.
- Project Claude guidance lives in repo `CLAUDE.md`.
- Global MCP lives in `~/.claude.json`.
- Project MCP lives in `.mcp.json`.
- Global skills live under `~/.claude/skills/`.
- Project skills live under repo `.claude/skills/`.

## Deferred Rules

- Do not treat `soul.md` as part of the generic baseline.
- Do not require host-level `systemPrompt` parity for the first pass.
- Do not assume VS Code cloud/remote exposes the same operator surface as the local Claude CLI or SDK.
- Do not assume `.claude/agents/` is part of the first-pass bootstrap.
