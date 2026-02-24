# Agent-Native Repo Audit Checklist

This checklist reflects one universal baseline for solo-developer, agent-written codebases.

## Checks
1. Root `AGENTS.md` exists.
2. Scoped `AGENTS.md` files exist (at least one in subdirectories).
3. `docs/` exists as system-of-record container.
4. `docs/projects/*/tasks.md` exists for resumable project execution.
5. Workflow automation exists (`.github/workflows/*.yml`).
6. CI quality gates are referenced in workflows (test/lint/typecheck).
7. Local guardrail config exists (`package.json`, `pyproject.toml`, or pre-commit).
8. Local skills exist (`.agents/skills/*/SKILL.md`) when workflows are repetitive.

## Scoring Weights
- Root AGENTS: 15
- Scoped AGENTS: 10
- docs/: 10
- tasks.md plans: 15
- workflows present: 10
- CI quality references: 20
- local guardrail config: 10
- local skills: 10

Total = 100.

## Interpretation
- 85-100: Strong agent-native foundation.
- 65-84: Functional but uneven; prioritize enforcement gaps.
- 40-64: Basic scaffolding exists; agent reliability will drift.
- 0-39: Not ready for autonomous agent-first execution.
