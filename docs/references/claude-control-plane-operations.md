# Claude Control Plane Operations

Use this page for the exact operator-facing facts of the local Claude control plane.

Use [Claude Control Plane](/Users/adi/.agents/docs/architecture/claude-control-plane.md) for the high-level shape.

## Canonical Inputs

- `claude/config/global.claude.md`
  - canonical source for `~/.claude/CLAUDE.md`
- `claude/config/settings.json`
  - canonical source for `~/.claude/settings.json`
- `claude/config/mcp.json`
  - canonical source for the managed global MCP entries
- `claude/config/repo-bootstrap.json`
  - canonical registry for per-repo Claude bootstrap

## Runtime Targets

- `~/.claude/CLAUDE.md`
  - global guidance file
- `~/.claude/settings.json`
  - permissive user/global defaults
- `~/.claude.json`
  - user runtime state and global MCP store
- repo `CLAUDE.md`
  - symlink to `AGENTS.md`
- repo `.claude/settings.json`
  - project settings
- repo `.mcp.json`
  - project MCP
- repo `.claude/skills/`
  - project skills

## First-Pass Commands

The Claude control plane is intended to follow the same sync/check pattern as Codex, with scripts living under `claude/scripts/`:

- `sync-global-claude-md.sh`
  - link `~/.claude/CLAUDE.md` to `claude/config/global.claude.md`
- `sync-settings.sh`
  - install the permissive global `settings.json` into `~/.claude/settings.json`
- `sync-global-mcp.sh`
  - merge managed `mcpServers` entries into `~/.claude.json`
- `sync-skills.sh`
  - materialize global and project Claude skills from `skills/registry.json`
- `sync-repo-claude-configs.sh`
  - render repo-local `CLAUDE.md -> AGENTS.md`, `.claude/settings.json`, and `.mcp.json`
- `bootstrap-machine-claude.sh`
  - run the full Claude apply batch
- `check-claude-control-plane.sh`
  - validate canonical inputs and rendered outputs

## Supported Manual Rules

- `CLAUDE.md` should be a symlink to `AGENTS.md` for the generic case.
- `AGENTS.md` remains the shared repo instruction source.
- `skipDangerousModePermissionPrompt` belongs in user/global Claude settings, not project settings.
- `enableAllProjectMcpServers` is part of the permissive global baseline.
- `sandbox.enabled = false` is the closest local no-sandbox default.

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
