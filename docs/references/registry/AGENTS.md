# Registry Views

This folder contains generated Obsidian views for browsing the control plane.

These files are user-facing lookup artifacts. They are not the source of truth and they do not drive sync behavior.

Canonical sources:

- [`skills/registry.json`](/Users/dobby/.agents/skills/registry.json)
- [`plugins/registry.json`](/Users/dobby/.agents/plugins/registry.json)
- [`codex/config/repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
- [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json)

Generated views:

- [`skills.base`](/Users/dobby/.agents/docs/references/registry/skills.base)
- [`skills-items/`](/Users/dobby/.agents/docs/references/registry/skills-items)
- [`plugins.base`](/Users/dobby/.agents/docs/references/registry/plugins.base)
- [`plugins-items/`](/Users/dobby/.agents/docs/references/registry/plugins-items)
- [`repo-bootstrap.base`](/Users/dobby/.agents/docs/references/registry/repo-bootstrap.base)
  - per-repo Codex bootstrap view, including MCP presets plus effective skill availability derived from [`skills/registry.json`](/Users/dobby/.agents/skills/registry.json)
- [`repo-bootstrap-items/`](/Users/dobby/.agents/docs/references/registry/repo-bootstrap-items)
- [`mcp-registry.base`](/Users/dobby/.agents/docs/references/registry/mcp-registry.base)
- [`mcp-registry-items/`](/Users/dobby/.agents/docs/references/registry/mcp-registry-items)

Validation:

- Run [`scripts/check-agent-control-planes.sh`](/Users/dobby/.agents/scripts/check-agent-control-planes.sh) before finishing changes that affect registry inputs.
