---
agent_name: "visual_reviewer"
effective_scope: "repo"
global_terminal: "false"
global_xcode: "false"
repos_csv: "adi"
model: "gpt-5.4"
reasoning: "medium"
sandbox_mode: "read-only"
web_search: "disabled"
js_repl: "true"
config_file: "agents/visual_reviewer.toml"
description: "Read-only reviewer for visual work such as screenshots, layouts, hierarchy, and clarity."
enabled_mcps:
  - "paper"
disabled_mcps:
  - "openaiDeveloperDocs"
enabled_tools: []
disabled_tools: []
enabled_features:
  - "js_repl"
disabled_features: []
repos:
  - "adi"
---

Generated from `codex/config/repo-bootstrap.json` plus the managed global Codex config templates. Do not edit manually.
