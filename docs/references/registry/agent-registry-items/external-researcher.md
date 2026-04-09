---
agent_name: "external-researcher"
effective_scope: "global"
access_profile: "read_only"
runtimes: "codex, claude"
global_terminal: "true"
global_xcode: "true"
global_claude: "true"
repos_csv: "-"
codex_name: "external_researcher"
codex_config_file: "agents/external_researcher.toml"
codex_model: "gpt-5.3-codex-spark"
codex_reasoning: "medium"
codex_sandbox_mode: "read-only"
codex_web_search: "-"
codex_js_repl: "-"
claude_name: "external-researcher"
claude_prompt_file: "external-researcher.md"
claude_model: "inherit"
claude_permission_mode: "-"
description: "Read-only researcher for information outside the local codebase and runtime."
codex_enabled_mcps: []
codex_disabled_mcps: []
codex_enabled_tools: []
codex_disabled_tools: []
codex_enabled_features: []
codex_disabled_features: []
claude_tools:
  - "Glob"
  - "Grep"
  - "Read"
  - "WebFetch"
claude_disallowed_tools: []
claude_skills: []
claude_mcp_servers: []
repos:
  - "-"
---

Generated from `agents/registry.json`, `codex/config/agents/*.toml`, and `claude/config/agents/*.md`. Do not edit manually.
