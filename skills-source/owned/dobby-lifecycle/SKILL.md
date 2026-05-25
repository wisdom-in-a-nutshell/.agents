---
name: dobby-lifecycle
description: "Operate Dobby workspace lifecycle hooks and context flow: session start boot context, user-prompt-submit time context, explicit thread consolidation, session-end handling, hook logs, and debugging why Dobby context/session memory did or did not load/write. Use for hook implementation changes, lifecycle debugging, boot context changes, and session continuity plumbing. For workspace/body routing use the `dobby-workspace` skill."
---

# Dobby Lifecycle

Dobby Lifecycle is the runtime context-flow layer for a Dobby workspace.

It owns the hook machinery that lets Dobby wake up with useful context, keep
per-turn context lightweight, and expose explicit thread consolidation when a
caller decides memory should be written.

## Boundary

Use this skill for:

- `SessionStart`, `UserPromptSubmit`, `PreCompact`, explicit `consolidate-thread`, `CodexThreadFinalize`, and `SessionEnd` behavior.
- Boot context assembly: shared `dobby-workspace` body map, `now.md`, recent sessions, Shelf snapshot, calendar snapshot, area manifest.
- Codex App Server thread consolidation and forked sidecar turns.
- Hook payload normalization, temporary hook records where active, worker logs, and lifecycle debugging.
- Questions like “why did Dobby not load context?”, “why did session memory not write?”, or “change what loads at boot.”

Do **not** use this skill for deciding where a fact belongs in memory. Use the
shared `dobby-workspace` body map for memory routing and file contracts.
Lifecycle code may read it when it needs memory meaning, especially during boot
and session finalization.

Use the more specific skills for concrete domains:

- personal open loops, tasks, reminders, deferrals → `dobby-shelf`
- calendar reads/writes/search/debugging → `dobby-calendar`
- structured journaling/check-ins → `journal-checkin`
- health data → `health`

## Hook scripts

Repo-local hook wrappers delegate to this skill’s scripts through the repo’s
`.agents/skills/dobby-lifecycle` symlink:

```text
scripts/hooks/session_start.py      -> scripts/hooks/session-start
scripts/hooks/user_prompt_submit.py -> scripts/hooks/user-prompt-submit
scripts/hooks/pre_compact.py        -> scripts/hooks/pre-compact
scripts/hooks/codex_thread_finalize.py -> scripts/hooks/codex-thread-finalize
scripts/hooks/session_end.py        -> scripts/hooks/session-end
```

The hook scripts live here:

```bash
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/session-start
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/user-prompt-submit
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/pre-compact
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/codex-thread-finalize
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/hooks/session-end
$HOME/.agents/skills-source/owned/dobby-lifecycle/scripts/consolidate-thread
```

## Reference files

Load on demand:

- `references/lifecycle-hooks.md` — boot, session notes, explicit thread consolidation, operational limits.

## Design principle

Name by domain, implement through hooks:

```text
dobby-workspace  = shared workspace body meaning and shape lint
dobby-lifecycle  = runtime context flow and hook machinery
```

Lifecycle is allowed to preserve and transport context. It should not become a
second memory router.
