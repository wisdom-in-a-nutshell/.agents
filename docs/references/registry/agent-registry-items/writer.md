---
agent_name: "writer"
effective_scope: "repo"
global_terminal: "false"
global_xcode: "false"
repos_csv: "adi,blog-personal"
model: "claude-4.6-sonnet"
reasoning: "medium"
sandbox_mode: "read-only"
web_search: "disabled"
js_repl: "false"
config_file: "agents/writer.toml"
description: "Writing-focused sub-agent. Highly encouraged for copywriting, rewriting, and tone-sensitive drafting."
enabled_mcps: []
disabled_mcps:
  - "openaiDeveloperDocs"
  - "paper"
enabled_tools: []
disabled_tools:
  - "view_image"
  - "web_search"
enabled_features: []
disabled_features:
  - "js_repl"
repos:
  - "adi"
  - "blog-personal"
---

Generated from `codex/config/repo-bootstrap.json` and `mcp/config/presets.json`. Do not edit manually.
