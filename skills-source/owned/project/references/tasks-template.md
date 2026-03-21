<!--
TEMPLATE GUIDANCE (for generating agent):
- Keep this as the single durable project file for create/resume/replan/close.
- Write as if a new agent will resume cold and should not need to rescan the repo.
- If critical project information is missing, ask before filling the plan with fake certainty.
- When the scoped work is clearly done, close out and archive directly instead of leaving a `ready-to-archive` holding state.
- Remove all HTML comments from the final output.
-->

# <Project Name>

## Goal
<!-- One sentence. Specific, testable, and outcome-focused. -->

## Why / Impact
<!-- Problem being solved, who benefits, and what fails if done wrong. -->

## Scope / Non-Goals
### In Scope
- 

### Out of Scope
- 

## Context / Constraints
<!-- Current state, key files, dependencies, constraints, external approvals, credentials, and relevant chat decisions. -->
- Date started: YYYY-MM-DD
- 

## Done When
<!-- Explicit pass conditions, demo flow, deliverables, or user-visible outcomes. -->
- [ ] 

## Milestones
<!-- Milestones should be checkpoint-sized. Include acceptance criteria and validation in the line itself. -->
- [ ] Milestone 1 — <deliverable>. Acceptance: <criteria>. Validate: `<command>`.

## Execution Rules
<!-- Keep these project-specific. Default behavior: keep diffs scoped, validate each milestone, fix failures before moving on, update this tracker continuously. -->
- Keep work scoped to the current milestone unless the tracker explicitly expands scope.
- Run validation after each milestone or risky batch and fix failures before advancing.
- Continue working until the scoped project is done or a true blocker requires human input; do not stop after one completed task if more actionable work remains.
- When `Done When` is satisfied and validation is acceptable, archive the project directly; ask only if completion is materially uncertain.
- Unless repo guidance says otherwise, archiving means moving the tracker to `docs/projects/archive/<project>/tasks.md`; create the archive folders if missing.
- Update this tracker whenever the plan changes materially or before ending the run.
- If project-critical ambiguity would stall progress later, ask targeted follow-up questions now and record the answers here.
- Use `Current Batch` as the live execution board and primary resume point.
- If parallel work helps, keep `tasks.md` single-writer and let delegated work write topic-based files under `docs/projects/<project>/resources/` when durable notes or artifacts are useful.

## Decisions
<!-- Record non-obvious choices and rationale so the next agent does not re-open them. -->
- 

## Open Questions / Blockers
<!-- Use "None." only when truly empty. -->
- None.

## Current Batch
<!-- Live execution board. Keep this small, usually 1-5 active items. This is the main resume point. Status values can be `todo`, `in_progress`, `delegated`, `blocked`, or `done`. `Role` can be `parent`, `explorer`, `external_researcher`, `worker`, or another explicit role. Link a topic-based file under `resources/` when durable notes or artifacts exist. -->
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| todo |  | parent |  |

## Backlog / Remaining Work
<!-- Durable list of remaining work. Promote items into Current Batch when they become active. Include at least one validation task, one AGENTS.md/doc review/update task when guidance changes materially, and a final closeout/archive task rather than a `ready-to-archive` placeholder. -->
- [ ] 

## Validation / Test Plan
<!-- Commands, expected results, manual checks, and milestone-specific verification notes. Prefer repo-local check scripts first; otherwise use pre-commit as the baseline when configured, plus task-specific tests/build checks. -->
- 

## Progress Log
<!-- Format: YYYY-MM-DD: [DONE|BLOCKED|IN-PROGRESS|DELEGATED] task or milestone — outcome -->
- YYYY-MM-DD: [IN-PROGRESS] Created or refreshed project tracker.
