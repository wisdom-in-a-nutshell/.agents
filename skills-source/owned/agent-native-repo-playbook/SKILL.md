---
name: agent-native-repo-playbook
description: Audits and improves repositories for a solo-developer, high-permission, agent-native workflow in which humans set intent and agents complete implementation, documentation, validation, and cleanup. Use for repository harness audits, readiness scoring, AGENTS or docs reviews, autonomous execution and proof-of-work loops, direct-to-main or YOLO safety, agent legibility, mechanical guardrails, and recurring agent drift.
---

# Agent-Native Repo Playbook

## Outcome

Make the repository a reliable harness in which a cold agent can take clear
intent through implementation, validation, product-facing proof, cleanup, and
reporting with minimal human coordination.

Operating model:

- Humans own intent, priorities, acceptance criteria, taste, and material risk.
- Agents own code, tests, docs, tooling, validation, cleanup, and routine
  follow-through.
- Repeated confusion or failure is a harness gap to fix, not a prompt to repeat.

Use recommendation-only mode for audit, review, score, or report requests. Edit
the repository only when the user asks for changes or implementation.

## Modes and References

Always read `references/best-practices.md`, then load only the task-specific
references:

- Scorecard: for a score, benchmark, readiness, or maturity assessment, read
  `references/harness-readiness-rubric.md`.
- Guidance: when reviewing or changing root or nested `AGENTS.md`, `STRUCTURE.md`,
  or equivalent guidance, read `references/agents-md-best-practices.md`.
- Docs: when reviewing or changing docs placement, architecture docs, or docs
  freshness rules, read `references/docs-structure-and-maintenance.md`.

## Workflow

1. Read the repo's sources of truth and execution surfaces:
   - root and relevant nested guidance;
   - structure maps, architecture, references, decisions, and active trackers;
   - workflows, build/test commands, `scripts/check-fast.sh`, and full checks;
   - relevant local skills, tools, logs, and product inspection paths.
2. Respect local contracts. Repo guidance and established architecture override
   this playbook's defaults.
3. Trace the full job from discovery to change, static validation, product or
   service proof, cleanup, reporting, and recovery. Identify where a cold agent
   would stall, guess, or need repeated human intervention.
4. Prioritize gaps that reduce coordination or turn repeated mistakes into
   mechanical feedback. Prefer a small working guardrail over more policy prose.
5. Match the requested action:
   - For an audit, recommend without editing.
   - For implementation, make the requested changes, update durable docs, and
     validate in proportion to risk.
6. Ground every major finding or completion claim in a file, command, log,
   screenshot, artifact, smoke test, or other concrete evidence.

## Output

For recommendation audits, return:

1. `What is working`.
2. `Highest-leverage gaps`.
3. `Guidance audit: Keep / Move / Delete` only when root guidance is in scope.
4. `Recommended next moves`: Immediate, Near-term, and Later.
5. `Evidence`: concrete file paths and relevant commands.

For scorecards, add the overall score and dimension table required by
`references/harness-readiness-rubric.md`.

For implementation, lead with the result and include checks run, product or
service proof when relevant, skipped validation with reasons, and any remaining
harness gap that weakened proof.

## Rules

- Preserve the model that humans set intent and agents write and maintain the
  implementation and repo docs.
- Prefer autonomous feedback loops, deterministic tools, and mechanical
  guardrails over reminders.
- Keep root guidance concise. Use it as a router; add nested guidance only where
  local boundary rules materially differ. Honor intentional alternatives such
  as `STRUCTURE.md`.
- Use the repo's docs contract. When none exists, prefer `docs/architecture/`
  for system shape and `docs/references/` for exact implementation facts.
- For a multi-repo system with a canonical orientation skill, keep cross-repo
  ownership and routing there while keeping implementation detail in the owning
  repo. Do not duplicate an architecture manual in the skill.
- Favor direct, recoverable workflows in trusted repos. Do not add team-heavy
  approvals, branch ceremony, or centralized policy layers without a concrete
  need or explicit request.
- Do not introduce centralized audit scripts unless the user explicitly asks.
- Use `$project` for durable project trackers and close or archive completed
  trackers according to repo guidance.

## Resources

- `references/best-practices.md`: canonical operating principles and default
  priorities.
- `references/harness-readiness-rubric.md`: scorecard dimensions and output
  contract.
- `references/agents-md-best-practices.md`: guidance quality gate and
  Keep / Move / Delete model.
- `references/docs-structure-and-maintenance.md`: lightweight docs contract and
  maintenance rules.
