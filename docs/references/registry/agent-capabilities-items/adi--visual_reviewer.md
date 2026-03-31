---
agent_name: "visual_reviewer"
scope_type: "repo"
repo_name: "adi"
model: "gpt-5.4"
reasoning: "medium"
sandbox_mode: "read-only"
web_search: "disabled"
js_repl: "-"
policy_binding: "visual_reviewer_paper_only"
config_file: "agents/visual_reviewer.toml"
enabled_mcps:
  - "paper"
disabled_mcps:
  - "openaiDeveloperDocs"
enabled_tools: []
disabled_tools: []
enabled_features: []
disabled_features: []
description: "Read-only reviewer for visual work such as screenshots, layouts, hierarchy, and clarity."
---

Generated from `codex/config/repo-bootstrap.json` plus the managed agent templates. Do not edit manually.
