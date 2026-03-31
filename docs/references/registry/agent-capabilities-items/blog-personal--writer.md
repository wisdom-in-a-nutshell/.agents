---
agent_name: "writer"
scope_type: "repo"
repo_name: "blog-personal"
model: "claude-4.6-sonnet"
reasoning: "medium"
sandbox_mode: "read-only"
web_search: "disabled"
js_repl: "false"
policy_binding: "writer_no_mcp"
config_file: "agents/writer.toml"
enabled_mcps: []
disabled_mcps:
  - "paper"
enabled_tools: []
disabled_tools:
  - "view_image"
  - "web_search"
enabled_features: []
disabled_features:
  - "js_repl"
description: "Writing-focused sub-agent for copywriting, rewriting, messaging, positioning, naming, summaries, and tone-sensitive drafting."
---

Generated from `codex/config/repo-bootstrap.json` plus the managed agent templates. Do not edit manually.
