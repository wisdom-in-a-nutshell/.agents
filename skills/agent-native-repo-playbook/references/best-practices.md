# Agent-Native Best Practices (Solo Dev)

This guide is based on the OpenAI harness-engineering model and adapted for a solo developer where agents write 100% of code.

## 1) Human intent, agent execution
- Keep humans focused on goals, acceptance criteria, and prioritization.
- Treat repeated agent failure as a system gap (missing docs, tools, guardrails), not a prompting problem.

## 2) AGENTS as map, not encyclopedia
- Keep `AGENTS.md` short and operational.
- Use it as an index to deeper docs, not as the full knowledge base.
- Add scoped `AGENTS.md` only where local patterns differ enough to prevent mistakes.

## 3) Repository is the system of record
- Put durable knowledge in versioned files inside the repo.
- Store plans, decisions, architecture notes, and operating rules in `docs/`.
- Do not rely on Slack/chat memory for agent-critical decisions.

## 4) Plans are first-class artifacts
- Use `docs/projects/<project>/tasks.md` for long-running work.
- Capture decisions and progress so any agent can resume cold.

## 5) Enforce invariants mechanically
- Encode boundaries and quality rules in CI/lints/tests.
- Favor explicit checks over “please follow this convention” prose.
- When a mistake repeats, add a guardrail.

## 6) Optimize for agent legibility
- Keep code layout predictable and discoverable.
- Make dependencies and interfaces explicit.
- Prefer stable, understandable tools and abstractions over opaque complexity.

## 7) Strengthen feedback loops
- Ensure agents can run the app/tests and verify fixes quickly.
- For relevant repos, expose UI state, logs, and metrics in ways agents can query.
- Prefer short fix loops over long blocked loops.

## 8) Continuous cleanup beats periodic cleanup
- Run recurring small cleanups for drift and stale docs.
- Promote review feedback into docs or tooling so improvements compound.

## 9) Keep process lightweight for solo speed
- Skip heavyweight team rituals unless needed.
- Standardize only what reduces repeat mistakes and handoff friction.
- Use one reusable playbook across repos for consistency.

## 10) Practical recommendation order
- First: clarify AGENTS/docs structure.
- Second: add or tighten CI/lint/test guardrails.
- Third: improve autonomous validation loops.
- Fourth: add recurring maintenance automation.

## Docs contract reference
- Use `references/docs-structure-and-maintenance.md` for the default `docs/architecture`, `docs/references`, and `docs/projects` layout and maintenance policy.
