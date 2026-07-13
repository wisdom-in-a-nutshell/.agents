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
- `clients: "all"` means Codex, Claude, and Copilot. `repos: "all"` means every repo in the managed inventory.
- Claude's managed project surface is root `.mcp.json`, which Copilot also discovers. A target may select Claude and Copilot together, but never Claude without Copilot.
- Codex targets render to `.codex/config.toml`; shared Claude/Copilot targets render to root `.mcp.json`; Copilot-only targets render to `.github/mcp.json`.
- Renderers may translate `transport` into runtime-specific output shapes.
