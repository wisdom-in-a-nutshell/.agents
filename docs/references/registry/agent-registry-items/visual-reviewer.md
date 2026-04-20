---
agent_name: "visual-reviewer"
effective_scope: "repo"
access_profile: "read_only"
runtimes: "codex, claude"
global_terminal: "false"
global_xcode: "false"
global_claude: "false"
repos_csv: "adi,adithyan-ai-videos,blog-personal"
codex_name: "visual_reviewer"
codex_config_file: "agents/visual_reviewer.toml"
codex_model: "gpt-5.4"
codex_reasoning: "medium"
codex_sandbox_mode: "read-only"
codex_web_search: "disabled"
codex_js_repl: "true"
claude_name: "visual-reviewer"
claude_prompt_file: "visual-reviewer.md"
claude_model: "inherit"
claude_permission_mode: "-"
description: "Read-only reviewer for visual work such as screenshots, layouts, hierarchy, and clarity."
codex_enabled_mcps: []
codex_disabled_mcps:
  - "openaiDeveloperDocs"
codex_enabled_tools: []
codex_disabled_tools: []
codex_enabled_features:
  - "js_repl"
codex_disabled_features: []
claude_tools:
  - "Glob"
  - "Grep"
  - "Read"
claude_disallowed_tools: []
claude_skills: []
claude_mcp_servers: []
repos:
  - "adi"
  - "adithyan-ai-videos"
  - "blog-personal"
---

Generated from `agents/registry.json`, `codex/config/agents/*.toml`, and `claude/config/agents/*.md`. Do not edit manually.
