---
name: symphony
description: Use when an agent is given a Symphony work item ID, needs to load the item from the Symphony task client, do the target repo work, and update lifecycle state as done, needs_input, failed, or cancelled. Also use when maintaining Symphony lifecycle behavior, task helper scripts, or the launchd watcher handoff contract.
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

1. When given a Symphony work item id, load it through the task client.
2. Read the target repo guidance from the loaded `repoPath`.
3. Do the work in the target repo according to local rules.
4. Run the most relevant validation the repo provides.
5. Follow the repo's normal finish path for commits, hooks, comments, and pushes.
6. Update Symphony lifecycle state through the task client before finishing.

## Task Client

Use the machine-primary client packaged in the Symphony repo. Prefer this direct Node CLI for all normal lifecycle reads and writes:

```bash
~/GitHub/symphony/dist/src/cli.js task <command> <work-id> --no-input
```

If the built CLI is missing, run:

```bash
cd ~/GitHub/symphony && npm run build -- --pretty false
```

Load the work item:

```bash
node ~/GitHub/symphony/dist/src/cli.js task get <work-id> --no-input
```

Get the minimal handoff prompt:

```bash
node ~/GitHub/symphony/dist/src/cli.js task prompt <work-id> --no-input --plain
```

Complete a work item:

```bash
printf '%s\n' "<human handoff>" \
  | node ~/GitHub/symphony/dist/src/cli.js task complete <work-id> --note-file - --no-input
```

Mark a work item blocked:

```bash
printf '%s\n' "<smallest useful request>" \
  | node ~/GitHub/symphony/dist/src/cli.js task needs-input <work-id> --note-file - --no-input
```

Mark a work item failed:

```bash
printf '%s\n' "<failure summary>" \
  | node ~/GitHub/symphony/dist/src/cli.js task failed <work-id> --note-file - --no-input
```

Record Adi's answer and make the item ready again:

```bash
printf '%s\n' "<Adi's answer>" \
  | node ~/GitHub/symphony/dist/src/cli.js task input <work-id> --note-file - --no-input
```

The client returns a stable JSON envelope with `schema_version`, `command`, `status`, `data`, `error`, and `meta`. Treat non-zero exit as a failed lifecycle write.

## Fallback Helper

Thin wrapper. Use this only when a shorter command is useful; if anything looks stuck or confusing, switch back to the direct Node CLI above.

```bash
$HOME/GitHub/agents/skills-source/owned/symphony/scripts/task
```

This wrapper forwards to `~/GitHub/symphony/dist/src/cli.js task ...` and preserves the same stable JSON envelope. Treat it as a fallback convenience path, not the first debugging path.

Load a work item:

```bash
"$HOME/GitHub/agents/skills-source/owned/symphony/scripts/task" get <work-id> --no-input
```

Complete a work item:

```bash
printf '%s\n' "<human handoff>" \
  | "$HOME/GitHub/agents/skills-source/owned/symphony/scripts/task" complete <work-id> --note-file - --no-input
```

Mark a work item blocked:

```bash
printf '%s\n' "<smallest useful request>" \
  | "$HOME/GitHub/agents/skills-source/owned/symphony/scripts/task" needs-input <work-id> --note-file - --no-input
```

Mark a work item failed:

```bash
printf '%s\n' "<failure summary>" \
  | "$HOME/GitHub/agents/skills-source/owned/symphony/scripts/task" failed <work-id> --note-file - --no-input
```

The helper updates Symphony state directly; it does not talk to Things. It has a short timeout by default and returns the same stable JSON envelope as the direct Node CLI.

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
