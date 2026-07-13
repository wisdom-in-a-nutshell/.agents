# Shared MCP Registry

Canonical shared MCP preset definitions live here.

## Purpose

- Keep one neutral MCP registry that every managed client renders from.
- Make each MCP's repository and client coverage explicit in one place.
- Prevent a server from being loaded outside the cells selected in that matrix.

## Source Of Truth

- `config/presets.json`
  - `presets`: canonical neutral MCP definitions plus their `targets`
  - each target selects `clients` and `repos`, using either `"all"` or a non-empty list

## Rules

- Use a neutral schema here; do not store runtime-specific blocks.
- Keep the managed repo inventory in `codex/config/repo-bootstrap.json`; keep all MCP assignment in this registry.
- `clients: "all"` means Codex, Claude, and Copilot. `repos: "all"` selects every managed repo; when paired exclusively with Copilot it also renders to Copilot's user MCP surface and therefore applies to every Copilot CLI workspace.
- Claude's managed project surface is root `.mcp.json`, which Copilot also discovers. A target may select Claude and Copilot together, but never Claude without Copilot.
- Codex targets render to `.codex/config.toml`; shared Claude/Copilot targets render to root `.mcp.json`; exclusive global Copilot targets render to `~/.copilot/mcp-config.json`; other Copilot-only targets render to `.github/mcp.json`.
- Copilot CLI 1.0.70 does not merge root `.mcp.json` with `.github/mcp.json` when both exist. The compiler rejects repo matrices that would rely on that merge.
- Renderers may translate `transport` into runtime-specific output shapes.
