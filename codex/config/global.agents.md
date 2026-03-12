# Global Agent Guidance (machine-wide)

> Prompts are often dictated via speech-to-text; interpret intent over literal spelling.

This file is machine-wide baseline guidance. Keep it generic and avoid portfolio-specific policy here.

## Scope Routing
- For repo best-practice recommendations, use [$agent-native-repo-playbook](/Users/adi/.agents/skills/agent-native-repo-playbook/SKILL.md).

## Global Defaults
- Prefer automation over manual repetition.
- Keep instructions concise, operational, and durable.
- Update the nearest `AGENTS.md` when a new repeatable pattern appears.
- When a change introduces durable behavior, architecture boundaries, or operational workflow that future work will rely on, offer to update the relevant repo docs in the same change.
- Follow the repo's docs routing guidance (typically `docs/AGENTS.md`) to decide whether the update belongs in architecture docs, reference docs, or project tracking docs.

## Git Automation (Codex Notify)
- This environment runs a notify hook after each agent turn that auto-stages, commits, and pushes.
- Do not run `git commit` or `git push` unless the user explicitly asks.
- Focus on making changes and reporting what changed; the hook handles the rest.

## Local Environment
- GitHub CLI (`gh`) is authenticated; use it freely for repo operations.
- Azure CLI (`az`) is authenticated; use it for Azure resource queries and management.
