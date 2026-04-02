# Registry Views

This folder contains generated Obsidian views for browsing the control plane.

These files are user-facing lookup artifacts. They are not the source of truth and they do not drive sync behavior.

Canonical sources:

- [`skills/registry.json`](/Users/dobby/.agents/skills/registry.json)
- [`codex/config/repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
- [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json)

Generated views:

- [`skills.base`](/Users/dobby/.agents/docs/references/registry/skills.base)
- [`repo-bootstrap.base`](/Users/dobby/.agents/docs/references/registry/repo-bootstrap.base)
  - per-repo Codex bootstrap view, including MCP presets plus effective skill availability derived from [`skills/registry.json`](/Users/dobby/.agents/skills/registry.json)
- [`agent-registry.base`](/Users/dobby/.agents/docs/references/registry/agent-registry.base)
  - role-centric Codex agent view, including scope, repos, model, sandbox, MCP exposure, web search, disabled tools, and `js_repl`
- [`mcp-registry.base`](/Users/dobby/.agents/docs/references/registry/mcp-registry.base)
