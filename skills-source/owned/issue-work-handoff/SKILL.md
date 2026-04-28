---
name: issue-work-handoff
description: Use when an agent is working from a GitHub issue, Things 3 task, tracker item, or DevWorker/Symphony-style task and needs to complete the work, report needs-input/blocked status, or produce a human-readable handoff. Applies to issue/task-driven implementation, investigation, validation, and review loops across repos.
---

# Issue Work Handoff

## Purpose

Use this skill to turn task-driven agent work into a clear human handoff. The goal is not to force a rigid template or tracker update; it is to leave enough context for a human or automation layer to understand what happened, what was validated, and what needs attention.

## Operating Model

- Treat the incoming task or issue as the coordination object. For the solo DevWorker workflow, Things 3 can be the whole coordination surface.
- Follow the target repo's `AGENTS.md`, docs, checks, and local workflow before this skill's preferences.
- Use available tools directly, especially `gh`, `git`, and repo-owned scripts, when the workflow calls for them.
- Keep orchestration metadata separate from the human summary.
- Do not paste raw logs, secrets, large diffs, or noisy diagnostics into handoffs or tracker updates.

## Default Bias

Work from the information provided. Do not stop to ask for input just because the task is underspecified; make reasonable assumptions, implement the safe parts, and write down important assumptions in the handoff.

Use `needs-input` only when progress is genuinely blocked, for example:

- A credential, account permission, device access, or external approval is required.
- Multiple plausible product decisions would lead to materially different outcomes.
- Continuing would risk data loss, destructive production changes, or violating repo guidance.
- Required source material is missing and cannot be inferred from the repo or task.

When blocked, ask for the smallest concrete input that would unblock the next run.

## Workflow

1. Read the task or issue and repo guidance.
2. Do the work in the current repo according to local rules.
3. Run the most relevant validation the repo provides.
4. Follow the repo's normal finish path for commits, hooks, comments, and pushes.
5. Finish with a human handoff that is useful to a collaborator or automation layer.

## Handoff

Write a concise handoff in your own words. Choose the shape that fits the result instead of forcing every heading every time.

Usually include:

- Outcome: completed, blocked, failed, or needs review.
- What changed: meaningful code, docs, config, or behavior changes.
- Validation: commands/checks run and whether they passed.
- Human attention: caveats, review focus, decisions needed, or why the work is blocked.
- Follow-up: only real follow-up, not generic next steps.

Keep the handoff human-first. If run metadata is useful, put it at the bottom under a short `Run details` section.

Good handoffs are specific enough to review without opening every file, but short enough to scan quickly.

## DevWorker Lifecycle

For the current solo DevWorker workflow, use this mental model:

- Things 3 is the human capture item and default coordination object.
- The `devworker` tag means the Mac mini worker should pick up the task.
- The `needs-input` tag means the worker is blocked and wants human involvement.
- The final agent message is the human handoff.
- DevWorker owns mechanical lifecycle updates.

This section is the canonical lifecycle contract. Repo docs may reference it, but should not duplicate these rules unless they are documenting exact CLI flags or implementation behavior.

Mechanical lifecycle:

- On pickup, DevWorker starts a Codex app-server thread and writes the raw run/session id to the Things note.
- While running, DevWorker may update the Things note with concise state, but should not create noisy receipts.
- On success, DevWorker writes the agent's final handoff to the Things note and completes the Things task.
- On blocked or failed work, DevWorker keeps the Things task open, adds `needs-input`, preserves the run/session id in the Things note, and leaves the smallest useful blocked note.
- GitHub issues are optional escalation, not the default path. Create or update one only when the task or repo workflow needs durable repo-native discussion, external review, or audit history.

On success, the handoff should be just the agent's useful final summary. Do not add a machine receipt, commit/check boilerplate, Things IDs, or "promoted from Things" metadata unless the user or repo specifically asks for it.

On blocked or failed work, keep the handoff focused on the smallest useful human decision or recovery step. The Things task should remain open with `needs-input`, and the run/session id should remain visible so the human can resume the thread.

## Completion

For completed work:

- Say what user-visible or system behavior changed.
- Mention important files or areas only when they help review.
- State validation honestly.
- If behavior depends on external availability, account permissions, rollout, or config, call that out.

## Blocked Or Failed Work

For blocked or failed work:

- Say the blocker plainly.
- Mention any local changes left behind, or say there are none.
- Ask for the smallest useful human decision or input.
- Avoid closing the issue or presenting the task as done.

## Tracker Updates

Do not post a GitHub comment or change tracker state by default. Do it only when one of these is true:

- The user explicitly asked for it.
- The issue or repo workflow says to update the tracker.
- The local automation depends on a tracker update for handoff.
- The work is blocked and the tracker is the right place to ask for human input.

When a tracker update is needed, prefer plain `gh` commands rather than a custom abstraction.

## Avoid

- Do not write a machine-only receipt as the main handoff.
- Do not include raw command output unless the exact output is necessary and already redacted.
- Do not bury the actual outcome under commit hashes, thread IDs, or check paths.
- Do not invent validation that did not run.
- Do not create new process rules when the repo already defines them.
