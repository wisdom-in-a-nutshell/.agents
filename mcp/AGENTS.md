# Shared MCP Registry

Canonical shared MCP preset definitions live here.

## Purpose

- Keep one neutral MCP registry that both Codex and Claude can render from.
- Keep repo assignment separate from MCP definition.
- Keep machine-wide default MCP enablement explicit.

## Source Of Truth

- `config/presets.json`
  - `presets`: canonical neutral MCP definitions
  - `global_presets`: machine-wide default MCP presets

## Rules

- Use a neutral schema here; do not store runtime-specific `claude` or `codex` blocks.
- Repo assignment belongs in `codex/config/repo-bootstrap.json`, not here.
- Renderers may translate `transport` into runtime-specific output shapes.
