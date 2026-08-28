# Agent-Native Best Practices (Solo Developer)

The repository, its docs, tools, checks, and feedback loops form the harness
around agents. Optimize that harness for solo velocity, agent reliability, fast
recovery, and verifiable outcomes.

## 1. Keep the human-agent boundary clear

- Humans set goals, acceptance criteria, taste, priorities, and material risk
  boundaries.
- Agents handle implementation, tests, docs, validation, cleanup, and routine
  follow-through.
- Escalate for judgment-heavy product tradeoffs, legal or safety risk, spending,
  secrets, and irreversible external effects—not routine implementation.

## 2. Design for the full job

A strong execution loop covers:

1. Discover the relevant sources of truth.
2. Plan enough to control risk and preserve intent.
3. Implement the complete change, including tests and docs.
4. Run fast static checks and focused tests.
5. Exercise the changed product, API, service, or workflow when relevant.
6. Inspect the result, repair failures, and rerun proof.
7. Clean temporary artifacts and report compact evidence.

Stopping after file edits is incomplete when the behavior can be exercised.

## 3. Make the repository the system of record

- Keep root guidance short and use it to route a cold agent to canonical docs,
  commands, and constraints.
- Put durable system shape in architecture docs and exact implementation facts
  in reference docs.
- Store active long-running execution state in the repo's project tracker, not
  chat history.
- Update docs with behavior changes and archive completed trackers promptly.

## 4. Convert repeated failure into harness improvements

- Treat repeated agent mistakes, human corrections, failed checks, broken
  deploys, and recurring confusion as evidence of a missing affordance.
- Fix the smallest durable layer that prevents recurrence: test, lint, type,
  script, clearer error, CLI contract, doc, or skill.
- Prefer one enforceable guardrail over repeating prompt text.
- When a gap cannot be fixed immediately, record it in the repo's lightweight
  debt or quality tracker if one exists.

## 5. Optimize tools and structure for agent legibility

- Keep layout predictable, dependencies explicit, boundaries discoverable, and
  shared invariants centralized.
- Prefer non-interactive, deterministic commands with stable exit codes and
  structured output where automation consumes results.
- Make failures actionable: include the command or operation, location, exit
  code, focused output, and likely remediation.
- Validate data shapes at boundaries instead of relying on guesses.
- Keep logs structured and queryable when agents need them for diagnosis.
- Prefer stable, understandable dependencies over opaque abstractions that make
  safe changes harder.

## 6. Require proof proportional to the change

- Report the commands, tests, logs, screenshots, artifact URLs, smoke results,
  or CI status that establish the result.
- Product and UI changes need product-facing proof when practical; static checks
  alone do not establish that the experience works.
- If a relevant proof path is unavailable, state why and identify the smallest
  harness improvement that would enable it next time.
- For risky changes, add a focused second-pass review after the primary checks.

## 7. Keep high-permission workflows recoverable

- Direct-to-main is the preferred default for trusted solo repositories unless
  local guidance says otherwise.
- Keep commit-time checks fast, deterministic, and actionable. Use a repo-owned
  `scripts/check-fast.sh` entrypoint and reserve slower checks for
  `scripts/check-full.sh` when that convention fits the repo.
- Use documented lifecycle automation for commit, rebase, and push rather than
  adding manual ceremony.
- Contain temporary and generated artifacts, keep rerun or rollback paths clear,
  and handle secrets or irreversible external effects with explicit boundaries.
- Add approval or branch process only when it meaningfully reduces real risk or
  improves recovery.

## 8. Strengthen short feedback loops

- Make it easy for agents to run the app, focused tests, and product smoke paths.
- Expose relevant UI state, service health, logs, and metrics through inspectable
  tools.
- Keep fast validation local; use CI and full checks for broader confidence.
- Repair flaky or ambiguous checks because unreliable feedback trains agents to
  ignore the harness.

## 9. Keep maintenance continuous and lightweight

- Update docs when behavior changes instead of deferring a documentation pass.
- Prefer recurring small cleanup of stale docs, dead paths, and drift over large
  periodic rewrites.
- Standardize only what reduces repeated mistakes or coordination load.
- Use one shared playbook across repos while allowing local contracts to win.

## 10. Recommended priority order

### Must have

- Clear context routing and durable repo knowledge.
- A full autonomous execution loop from intent through proof and cleanup.
- Fast mechanical guardrails for important invariants.
- Recoverable high-permission delivery.
- Evidence-backed completion reports.

### Good to have

- Product smoke paths agents can run directly.
- Recurring docs and drift cleanup.
- Lightweight debt tracking for unresolved harness gaps.
- Focused second-pass review for risky changes.

### Not by default

- Mandatory pull-request or branch ceremony for solo work.
- Heavy approval queues detached from actual risk.
- Central policy layers that duplicate repo-owned contracts.
- More docs, skills, or automation than agents can reliably discover and use.
