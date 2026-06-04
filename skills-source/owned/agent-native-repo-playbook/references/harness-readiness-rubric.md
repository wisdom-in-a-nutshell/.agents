# Harness Readiness Rubric

Use this rubric when the user asks to score, benchmark, audit, or compare a repo's agent-native readiness.

## Scoring

Score each dimension from 0 to 4.

- `0`: missing or actively harmful.
- `1`: present as prose or ad hoc habit, but not reliable.
- `2`: usable in common cases, with visible gaps.
- `3`: documented and repeatable for most relevant work.
- `4`: mechanically supported, easy for a cold agent to run, and improved when failures repeat.

## Dimensions

### Context Routing
- Does a cold agent know which files to read first?
- Are `AGENTS.md`, repo maps, and local docs short, current, and non-duplicative?
- Do nested rules exist only where local boundary rules materially differ?

### Durable Repo Knowledge
- Are architecture, reference facts, active plans, and decisions stored in repo docs?
- Are volatile instructions kept out of root guidance?
- Do docs change with behavior changes?

### Autonomous Execution Loop
- Can the agent continue from intent to implementation, validation, docs, and cleanup without frequent human prompting?
- Are escalation boundaries clear?
- Does the repo favor full-job completion over stopping at partial changes?

### Mechanical Guardrails
- Are important invariants enforced by tests, lints, scripts, hooks, or CI?
- Are `scripts/check-fast.sh` and slower full checks available where appropriate?
- Are repeated mistakes converted into durable enforcement?

### Proof Of Work
- Does meaningful work end with compact evidence of what was run or inspected?
- Are product paths smoked through CLI, API, browser, screenshots, logs, artifacts, or CI when relevant?
- Are skipped checks named with a reason?

### Recovery And YOLO Safety
- Does the repo support high-permission rapid work without fragile manual recovery?
- Are temporary files contained, generated artifacts understood, and rollback or re-run paths documented?
- Are secrets and irreversible external effects handled with explicit boundaries?

### Feedback-To-Harness Compounding
- Do human corrections, failed checks, broken deploys, flaky tests, or repeated confusion become docs, tools, tests, skills, or clearer errors?
- Is there a lightweight place to record harness gaps when they cannot be fixed immediately?

## Output Shape

For scorecard audits, return:

1. Overall score: `N/100`.
2. Dimension table: score, evidence, and one-line rationale.
3. Top blockers: highest-leverage gaps that limit agent autonomy.
4. Next moves:
   - Immediate: low effort, high leverage.
   - Near-term: medium effort or cross-cutting.
   - Later: useful after the core loop is stronger.
5. Evidence: concrete file paths and commands inspected.

Weight proof, autonomous execution, and mechanical guardrails heavily for solo high-permission repos. Do not penalize a repo for skipping enterprise process when the repo has fast recovery and clear proof loops.
