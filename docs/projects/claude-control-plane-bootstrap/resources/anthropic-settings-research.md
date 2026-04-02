# Anthropic Settings Research

Official Anthropic docs show that Claude has separate user/global, project, local, and managed settings layers.

## Verified Facts

- User/global settings live in `~/.claude/settings.json`.
- Project settings live in `.claude/settings.json`.
- Local private settings live in `.claude/settings.local.json`.
- Managed settings have higher precedence than project and user settings.
- `permissions.defaultMode = "bypassPermissions"` is the broad permissive mode for approvals.
- `sandbox.enabled = false` is the closest local no-sandbox posture.
- `skipDangerousModePermissionPrompt` exists in docs, but Anthropic says it is ignored in project settings and belongs at user/global scope.
- Project MCP lives in `.mcp.json`.
- User/global MCP lives in `~/.claude.json`.
- The published settings schema is helpful, but it does not always expose every doc-backed key.

## Bootstrap Consequences

- Put permissive defaults in global user settings.
- Keep project settings minimal and project-specific.
- Treat schema/docs mismatches as real and do not assume the schema is exhaustive.
- Use `.mcp.json` for repo MCP and `~/.claude.json` for machine-wide MCP/runtime state.

## Sources

- https://code.claude.com/docs/en/settings
- https://code.claude.com/docs/en/mcp
- https://code.claude.com/docs/en/permissions
- https://www.schemastore.org/claude-code-settings.json
