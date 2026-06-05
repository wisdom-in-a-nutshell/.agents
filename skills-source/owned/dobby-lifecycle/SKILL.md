---
name: dobby-lifecycle
description: "Operate Dobby workspace lifecycle hooks and context flow: session start boot context, user-prompt-submit time context, explicit thread finalization, and debugging why Dobby context/session memory did or did not load/write. Use for hook implementation changes, lifecycle debugging, boot context changes, and session continuity plumbing. For workspace/body routing use the `dobby-workspace` skill."
---

# Dobby Lifecycle

Dobby Lifecycle is the runtime context-flow layer for a Dobby workspace.

It owns the hook machinery that lets Dobby wake up with useful context, keep
per-turn context lightweight, and expose explicit Codex thread finalization when
a caller decides a thread should preserve useful memory before archive.

## Boundary

Use this skill for:

- `SessionStart`, `UserPromptSubmit`, and `FinalizeCodexThread` behavior.
- Boot context assembly: shared `dobby-workspace` body map, `memory/now.json`, recent session-memory summaries, Shelf snapshot, calendar snapshot, area manifest.
- Codex App Server same-thread remember-session flow before archive.
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
scripts/hooks/finalize_codex_thread.py -> scripts/hooks/finalize-codex-thread
```

The hook scripts live here:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/hooks/session-start
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/hooks/user-prompt-submit
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/hooks/finalize-codex-thread
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/remember-session
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/session-memory
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/validate
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/prompts/remember-session.md
```

`scripts/validate` is the public validator facade for lifecycle-owned workspace
files. It delegates session-memory records to `session-memory validate`, which
remains the schema source of truth.

## Reference files

Load on demand:

- `references/lifecycle-hooks.md` — boot, session memory, explicit thread finalization, operational limits.

## Design principle

Name by domain, implement through hooks:

```text
dobby-workspace  = shared workspace body meaning, memory routing, and shape lint
dobby-lifecycle  = runtime context flow, boot loading, and finalization plumbing
```

Lifecycle is allowed to preserve and transport context. It may read the
workspace body map, but it should not become a second memory router.
