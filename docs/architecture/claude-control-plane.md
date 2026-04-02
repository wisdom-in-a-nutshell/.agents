# Claude Control Plane

This repo now carries a sibling personal control plane for Claude. The rule is the same one used for Codex: keep durable source in `~/.agents`, keep the applied runtime in `~/.claude`, and keep repo-local behavior close to the repo that needs it.

The first pass is local-only and generic. It does not try to solve the `adi` `soul.md` prompt override yet.

## Figure 1: Ownership Layout

```mermaid
flowchart TD
    A[~/.agents<br/>canonical Claude control plane]
    B[~/.claude<br/>applied runtime home]
    C[Repo-local CLAUDE.md / .claude / .mcp.json]
    D[Codex control plane]

    A --> B
    A --> C
    D --- A
```

## Main Parts

### `~/.agents/claude`

Owns the canonical Claude bootstrap inputs:

- `config/global.claude.md`
- `config/settings.json`
- `config/mcp.json`
- `config/repo-bootstrap.json`
- `scripts/` for sync and validation entrypoints

### `~/.claude`

Owns the applied local runtime state:

- `CLAUDE.md`
- `settings.json`
- `settings.local.json`
- `skills/`
- `agents/`
- `*.json` runtime caches and history

### Repo-local files

The generic project contract is:

- `CLAUDE.md -> AGENTS.md`
- `.claude/settings.json`
- `.mcp.json`
- `.claude/skills/`

`AGENTS.md` remains the shared repo instruction source. `CLAUDE.md` is only the compatibility entrypoint.

## Layering

Claude has both global and project layers:

- global `~/.claude/CLAUDE.md`
- global `~/.claude/settings.json`
- global `~/.claude.json` for user MCP/runtime state
- project `CLAUDE.md`
- project `.claude/settings.json`
- project `.mcp.json`
- project `.claude/skills/`

The first pass keeps the same permissive default posture at both scopes where Anthropic allows it:

- `permissions.defaultMode = "bypassPermissions"`
- `sandbox.enabled = false`
- `skipDangerousModePermissionPrompt = true` at user/global scope

## First-Pass Scope

This baseline includes:

- `CLAUDE.md -> AGENTS.md` for generic repo compatibility
- permissive Claude settings
- project MCP via `.mcp.json`
- global MCP via `~/.claude.json`
- global and project skills

This baseline intentionally defers:

- the `adi` `soul.md` special case
- host/runtime `systemPrompt` replacement parity
- VS Code cloud/remote agent behavior
- Claude subagent materialization under `.claude/agents/`
- any repo-specific Claude prompt override that would fork the generic model

## Model

The mental model is:

1. `AGENTS.md` stays the shared repo contract.
2. Claude compatibility is added on top of it.
3. `~/.agents/claude/` defines the managed canonical inputs.
4. `~/.claude/` is the applied machine state.

That keeps Claude as a sibling control plane, not a replacement for the existing Codex bootstrap.

## Related Docs

- [Claude Control Plane Operations](/Users/adi/.agents/docs/references/claude-control-plane-operations.md)
- [Anthropic Settings Research](/Users/adi/.agents/docs/projects/claude-control-plane-bootstrap/resources/anthropic-settings-research.md)
- [Anthropic Agent Surfaces Research](/Users/adi/.agents/docs/projects/claude-control-plane-bootstrap/resources/anthropic-agent-surfaces.md)
