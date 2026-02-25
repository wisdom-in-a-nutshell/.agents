# AGENTS.md Best Practices (Agent-First, Solo)

## Core operating principle
- Human sets intent and priorities.
- Agents write 100% of code and maintain repository docs.

## Purpose of AGENTS.md
- Onboard a cold agent fast.
- Route the agent to the right source of truth.
- State durable, operational constraints.

AGENTS is a map, not the full knowledge base.

## Root vs nested AGENTS

### Root AGENTS.md
- Keep as the router and precedence contract.
- Include only universal rules that apply to most tasks.
- Point to deeper docs (`docs/decisions`, `docs/projects`, architecture docs).

### Nested AGENTS.md
- Add only where local boundary rules materially differ from parent scope.
- Use for ownership boundaries and local do/do-not rules.
- Avoid volatile runbook details that change frequently.

## AGENTS quality gate (for each line/section)
- Universal: does this apply to most tasks in this scope?
- Operational: does it change behavior in a clear way?
- Enforceable: can we verify this with tooling/checks?
- Durable: likely still true in weeks, not just today?
- Best location: should this live in decisions/projects/docs instead?

If a line fails multiple checks, move or delete it.

## Keep / Move / Delete audit model

### Keep
- Boundary rules, precedence, hard constraints, required tooling sources.

### Move
- Deep rationale -> `docs/decisions/*`
- Active execution state -> `docs/projects/<project>/tasks.md`
- Setup/runbook/how-to detail -> `docs/setup/*` or scoped docs

### Delete
- Redundant restatements of existing rules.
- Task-specific temporary instructions.
- Style reminders better enforced by lint/format/CI.

## Nested AGENTS decision test
- Add nested AGENTS only if both are true:
  - Local mistakes keep recurring in that subtree.
  - A short local rule would have prevented those mistakes.

Otherwise rely on root AGENTS + docs.

## Anti-patterns
- Turning AGENTS into an encyclopedia.
- Packing AGENTS with style/lint prose instead of mechanical checks.
- Repeating the same rule in many AGENTS files.
- Keeping stale instructions after architecture changes.

## Practical target
- Root AGENTS: short router.
- Nested AGENTS: short boundary rules.
- Detailed knowledge: in `docs/`, linked from AGENTS.
