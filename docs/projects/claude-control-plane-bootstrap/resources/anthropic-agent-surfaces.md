# Anthropic Agent Surfaces Research

Official Anthropic docs split Claude behavior across repo files, skills, agents, and host/runtime prompt controls.

## Verified Facts

- `CLAUDE.md` is the repo instruction surface.
- `CLAUDE.md` can import other files with `@path` syntax.
- Anthropic recommends `CLAUDE.md` as the place to pull in `AGENTS.md` when both ecosystems need to share repo guidance.
- `CLAUDE.md` is loaded as context, not as a replacement for the built-in Claude Code system prompt.
- User skills live in `~/.claude/skills/<skill>/SKILL.md`.
- Project skills live in `.claude/skills/<skill>/SKILL.md`.
- User agents live in `~/.claude/agents/`.
- Project agents live in `.claude/agents/`.
- The Agent SDK exposes `systemPrompt` and `settingSources` as host/runtime controls.
- Full `model_instructions_file` style replacement is a host/runtime concern, not a normal repo setting.
- Preserving Claude Code behavior while adding custom instruction text is done through the SDK prompt APIs, not through `CLAUDE.md` alone.

## Bootstrap Consequences

- Use `CLAUDE.md` with `@AGENTS.md` for the generic repo case.
- Keep prompt-replacement parity out of the first generic pass.
- Treat skills and agents as first-class Claude surfaces, but keep them registry-driven and repo-local where needed.
- Defer the `adi` `soul.md` override until the generic baseline is stable.

## Sources

- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/subagents
- https://platform.claude.com/docs/en/agent-sdk/overview
- https://platform.claude.com/docs/en/agent-sdk/modifying-system-prompts
