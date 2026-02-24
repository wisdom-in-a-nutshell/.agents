# Agent-Native Best Practices (Solo Dev)

This guide is based on the OpenAI harness-engineering model and adapted for a solo developer where agents write 100% of code.

## Base principle
- Optimize for solo velocity with agent reliability: minimal process, strong repo legibility, and targeted mechanical guardrails.

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
- Use `references/docs-structure-and-maintenance.md` for the minimum `docs/architecture`, `docs/references`, and `docs/projects` layout and maintenance policy.

## 11) Merge philosophy (solo rapid-main)
- Direct-to-main is the default and preferred workflow.
- Do not introduce branch-heavy flow unless explicitly requested.
- Keep pre-commit checks and CI checks focused and fast so iteration stays high-velocity.
- Use the notify automation loop (auto commit, pull --rebase, push) as the standard shipping path.

## 12) Agent self-review loop
- Before push: run local checks, inspect diff, address obvious issues, re-run checks.
- For riskier changes, add an explicit second-pass agent review before final push.

## 13) Promote repeated failures into enforcement
- If a mistake repeats, convert it into a mechanical check (lint/test/script/CI rule).
- Prefer one durable guardrail over repeated reminder text.

## 14) Golden principles (recommended defaults)
- Do not rely on guessed data shapes; validate at boundaries.
- Keep shared invariants centralized (avoid copy-pasted ad-hoc helpers).
- Keep logs structured and actionable for agents.

## 15) Docs freshness loop
- Run recurring docs cleanup to catch stale instructions and drift.
- Update docs at the same time behavior changes; do not defer doc updates indefinitely.

## 16) Quality and debt tracking
- Keep a lightweight quality/debt tracker for recurring weak spots.
- Prefer continuous small refactors over periodic large cleanup bursts.

## 17) Escalation policy
- Escalate to human for judgment-heavy decisions (product tradeoffs, legal/risk, high-cost decisions).
- Continue autonomously for implementation and low-risk refactors.

## 18) Dependency selection rule
- Prefer stable, legible dependencies and abstractions agents can reason about.
- Avoid opaque frameworks when they reduce agent reliability.

## 19) Priority tiers for this workflow

### Must-have
- Human intent, agent execution as the default operating model.
- `AGENTS.md` as map and `docs/` as system of record.
- `docs/projects/<project>/tasks.md` workflow via `$project-planner` and `$project-executor`.
- Fast mechanical guardrails (pre-commit, lint/test/typecheck where applicable).
- Direct-to-main automation loop with commit/pull-rebase/push on each agent turn.
- Docs update discipline: behavior changes and docs changes ship together.

### Good-to-have
- Repo checks for docs contract compliance.
- Recurring doc-gardening and drift cleanup automation.
- Lightweight quality/debt score tracking.
- Explicit second-pass agent review on risky changes.

### Not-now by default
- Worktree isolation.
- Branch-heavy team process.
- Heavy approval gates that slow solo flow.
