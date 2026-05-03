---
name: symphony
description: Use when an agent is working from a Symphony work item or local solo-dev agent queue, needs to finish with a Symphony status footer, report needs_input, complete a work item, or produce a concise human handoff. Also use when maintaining Symphony lifecycle behavior, its task helper, or the launchd watcher handoff contract.
---

# Symphony

## Purpose

Use this skill to keep solo agent work connected to Symphony's queue and lifecycle. Symphony is the operational layer for work items that Codex can run through App Server while Adi keeps visibility in the Mac app and later in Dobby.

## Operating Model

- Treat the Symphony work item as the coordination object when one is present.
- Follow the target repo's `AGENTS.md`, docs, checks, and local workflow before this skill's preferences.
- Use the real repo working directory so Codex Mac app sessions remain visible and resumable.
- Keep Symphony metadata separate from the human handoff.
- Do not write Symphony lifecycle state to Things 3. Things is legacy input only when a task explicitly comes from Things.
- Do not paste raw logs, secrets, large diffs, or noisy diagnostics into handoffs.

## Lifecycle

Symphony states:

- `ready`: work can be picked up.
- `running`: Codex is actively working.
- `needs_input`: blocked on Adi.
- `done`: Codex considers the work complete.
- `failed`: execution failed.
- `cancelled`: intentionally stopped.

There is no `needs_review` state. In the solo agent-native loop, if Codex believes the task is ready, the Symphony item is `done`; the final handoff can still mention caveats and validation gaps.

Use `needs_input` only when progress is genuinely blocked, for example:

- A credential, account permission, device access, or external approval is required.
- Multiple plausible product decisions would lead to materially different outcomes.
- Continuing would risk data loss, destructive production changes, or violating repo guidance.
- Required source material is missing and cannot be inferred from the repo or task.

When blocked, ask for the smallest concrete input that would unblock the next run.

## Workflow

1. Read the work item and repo guidance.
2. Do the work in the current repo according to local rules.
3. Run the most relevant validation the repo provides.
4. Follow the repo's normal finish path for commits, hooks, comments, and pushes.
5. Finish with a human handoff plus the Symphony footer when running under Symphony.

## Symphony Footer

When Symphony is supervising the run, finish with this machine-readable footer:

```text
SYMPHONY_STATUS: done | needs_input | failed
SYMPHONY_SUMMARY: one concise sentence
SYMPHONY_INPUT: only when status is needs_input; ask the specific blocking question
```

If no footer is found after a successful Codex turn, Symphony defaults to `done`, so include the footer when the status is blocked or failed.

## Helper Contract

Script:

```bash
$HOME/.agents/skills-source/owned/symphony/scripts/task
```

Complete a work item:

```bash
printf '%s\n' "<human handoff>" \
  | "$HOME/.agents/skills-source/owned/symphony/scripts/task" complete <work-id> --note-file - --no-input
```

Mark a work item blocked:

```bash
printf '%s\n' "<smallest useful request>" \
  | "$HOME/.agents/skills-source/owned/symphony/scripts/task" needs-input <work-id> --note-file - --no-input
```

The helper emits JSON with `status: "ok"` or `status: "error"`. It updates Symphony state directly; it does not talk to Things.

## Handoff Shape

Write a concise handoff in your own words. Choose the shape that fits the result instead of forcing every heading every time.

Usually include:

- Outcome: completed, blocked, or failed.
- What changed: meaningful code, docs, config, or behavior changes.
- Validation: commands/checks run and whether they passed.
- Human attention: caveats, decisions needed, or why the work is blocked.
- Follow-up: only real follow-up, not generic next steps.

Keep the handoff human-first. If run metadata is useful, put it at the bottom under a short `Run details` section.

## Avoid

- Do not treat Things 3 as the Symphony coordination surface.
- Do not create a review state or ask for manual review as a lifecycle requirement.
- Do not write a machine-only receipt as the main handoff.
- Do not bury the actual outcome under commit hashes, thread IDs, or check paths.
- Do not invent validation that did not run.
- Do not create new process rules when the repo already defines them.
