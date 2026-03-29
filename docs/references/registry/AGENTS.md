# Registry Views

This folder contains generated Obsidian views for browsing the control plane.

These files are user-facing lookup artifacts. They are not the source of truth and they do not drive sync behavior.

Canonical sources:

- [`skills/registry.json`](/Users/dobby/.agents/skills/registry.json)
- [`codex/config/repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)

Generated views:

- [`skills.base`](/Users/dobby/.agents/docs/references/registry/skills.base)
- [`repo-bootstrap.base`](/Users/dobby/.agents/docs/references/registry/repo-bootstrap.base)
  - per-repo Codex bootstrap view, including MCP presets plus effective skill availability derived from [`skills/registry.json`](/Users/dobby/.agents/skills/registry.json)
- [`mcp-registry.base`](/Users/dobby/.agents/docs/references/registry/mcp-registry.base)
