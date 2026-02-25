<!--
TEMPLATE GUIDANCE (for generating agent):
- These are guidelines, not rigid rules. Adapt to the project's needs.
- When in doubt, err on the side of being MORE descriptive — over-describing is far better than under-describing for agent handoff.
- A new dev/agent should understand the project and start working without scanning the repo.
- Replace each section's comment with actual content; remove all HTML comments in final output.
- When referencing code, include file paths and patterns to follow.

SPECIFICITY: Match detail level to task fragility:
- Fragile/exact steps (DB migrations, deployments, API contracts): Be very prescriptive with exact commands
- Judgment calls (refactoring, naming, structure): Leave room for agent decisions
-->

# <Project Name>

## Goal
<!-- One sentence: what does "done" look like? Specific and testable. -->

## Why / Impact
<!-- 
- Problem being solved (1-2 sentences)
- Who benefits and how (1 sentence)
- What breaks if done wrong (1 sentence)
These are minimums — expand if the context is complex.
-->

## Context
<!--
- Starting point: what exists now, key files, entry points
- Technical constraints: must use X, can't use Y
- Relevant decisions from discussion (capture chat context here)
Be thorough — this saves the next agent from repo scanning.
-->

## Decisions
<!-- Choices made with brief rationale. This is conversation memory — the "why" behind each choice so the next agent doesn't re-ask. Include alternatives considered if relevant. -->

## Open Questions
<!-- Unresolved items that block progress. If empty, state "None." -->

## Tasks
<!--
FORMAT: Verb + what + where (file path) + how (pattern/reference)
ORDER: Execution order; each task assumes previous are done
GRANULARITY: One task = one focused session (10-30 min). Split if:
  - Touches 3+ unrelated files
  - Contains "and" joining distinct actions
  - No single clear starting file
MUST INCLUDE: validation task, AGENTS.md review task, archive task (last)
PARALLEL: Mark only truly independent tasks as parallel-capable. Use one orchestrator to merge outputs and update tasks.md.

Be specific — "Add X to Y following Z pattern" beats "Add X"
-->
- [ ] 

## Validation / Test Plan
<!-- How to verify done: commands to run, expected output, or manual checks. Be explicit about what "passing" looks like. -->

## Progress Log
<!-- Format: YYYY-MM-DD: [DONE|BLOCKED|IN-PROGRESS] task — outcome/note -->
- YYYY-MM-DD: Created plan.

## Next 3 Actions
<!-- 
RESUME POINT: Any agent picking this up starts here.
Keep self-contained — actionable without reading full doc.
Update after each completed task or any stop.
-->
1. 
2. 
3.
