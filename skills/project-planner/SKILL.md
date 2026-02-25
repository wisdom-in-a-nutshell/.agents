---
name: project-planner
description: Create or update a long-running project plan and task tracker in docs/projects/PROJECT/tasks.md. Use when starting a new project, setting up a resumable plan, or refreshing the project state across sessions. Ask minimal clarifying questions, then write or update the per-project tasks.md with clear goals, context, decisions, tasks, and next actions.
---

# Project Planner

## Overview
Create or update a per-project tasks file that serves as the single source of truth for long-running work and enables clean resume across sessions.

## Default location
1. Check repo guidance (AGENTS.md, docs) for a prescribed location or format.
2. If none exists, use: `docs/projects/<project>/tasks.md`.

## Workflow
1. **Identify the project**
   - Use an existing project folder if referenced; otherwise derive a kebab-case name.
2. **Check for an existing tasks.md**
   - If present, update it; if not, create it using the template in `references/tasks-template.md`.
   - Path note: `references/tasks-template.md` is relative to *this skill directory* (i.e. `~/.agents/skills/project-planner/references/tasks-template.md`), not a path inside the target repo.
3. **Ask only essential questions** (1-3 max)
   - Goal/scope, constraints, success criteria, deadline are the usual minimums.
   - If details are missing but not blocking, make a reasonable assumption and proceed.
4. **Populate or update sections**
   - Follow the inline guidance (HTML comments) in `references/tasks-template.md` for each section.
   - When in doubt, err on being MORE descriptive — over-describing is far better than under-describing for agent handoff.
   - Write as if a new developer/agent will read this cold — include enough detail that they can start work without re-scanning the codebase.
   - Capture decisions and context from the chat conversation so the next agent doesn't re-ask.
   - Always add a task to review/update `AGENTS.md` in relevant folders. If no update is needed, the task should explicitly confirm that and close out.
   - Place that task near the end of the list (after implementation tasks, before final validation/commit).
5. **Align with local rules**
   - If repo guidance requires an archive step or specific sections, include them.

## Output rules
- Write or update `tasks.md` directly.
- After creating or updating `tasks.md`, offer to proceed with execution using `$project-executor`.
- Suggested handoff line: "Want me to continue this project with `$project-executor` (the companion execution skill)?"

## Section expectations
See `references/tasks-template.md` for required sections and inline guidance for each. Minimum sections:
- Goal
- Why / Impact
- Context
- Decisions
- Open Questions
- Tasks (checkbox list)
- Validation / Test Plan
- Progress Log (dated entries)
- Next 3 Actions (this is the resume point for any agent picking up the project)

## Task list guidance
- Use verb-first checklist items.
- Include at least one validation/testing task when applicable.
- Include handoff details inside tasks: exact file paths to edit/create, integration hook points, storage paths/prefixes, DB fields touched, and external function signatures/return shapes.
- Mark tasks that can run in parallel when they are truly independent (no shared file/contract dependency).
- For parallel-capable plans, include an orchestrator step that consolidates worker outputs and updates `tasks.md`.
- Include an `AGENTS.md` review/update task for every long-running project; close it by either updating/adding guidance or explicitly noting no change needed.
- Always add an archive task as the final checklist item (after the AGENTS task). Move to `docs/projects/archive/<project>/` when the user agrees.
- Write tasks so an executor can run multiple tasks in sequence without waiting for user confirmation between minor steps.
- Include explicit blocker/escalation notes only for decisions that truly require human judgment (product tradeoff, risk, credentials, external approvals).

## Resources
- Use `references/tasks-template.md` (relative to this skill directory) when creating a new tasks file or normalizing a missing section.
- The template contains HTML comments with guidance for each section — read them, then strip all comments in the final output.
