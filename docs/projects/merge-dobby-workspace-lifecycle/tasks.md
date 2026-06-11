# Merge dobby-lifecycle into dobby-workspace

## Goal
One skill — `dobby-workspace` — owns both the workspace shape (body map, linter) and its lifecycle (boot, per-turn, finalize, session memory, dreaming); `dobby-lifecycle` ceases to exist, with every external caller repointed and no old paths left behind.

## Why / Impact
Evidence from the 2026-06-11 memory-format migration: every batch touched both skills together — the boundary is fake (anatomy vs metabolism in theory, one module in practice). The split also caused a real staleness bug (body map describing lifecycle's session contract drifted). Risk if done wrong: boot hooks, finalize jobs, or the dream job silently stop firing.

## Scope / Non-Goals
### In Scope
- Move all of `skills-source/owned/dobby-lifecycle/` (scripts, hooks, prompts, references, agents, tests) into `skills-source/owned/dobby-workspace/`.
- Repoint every external consumer (checklist below); regenerate surfaces in all managed repos; delete the old skill directory.
- Merge SKILL.md descriptions/triggers into one coherent skill doc; one tests/run.sh.
- Apply the one-home doc rule while merging: body map points to contracts, never re-describes other skills'.
### Out of Scope
- Behavior changes of any kind (boot content, finalize semantics, dreaming policy).
- Renaming other skills; gateway code changes beyond config/docs.

## Context / Constraints
- Date started: 2026-06-11 (tracker created; execution not started).
- Direction: keep the `dobby-workspace` name (describes merged scope); retire `dobby-lifecycle`.
- No dual paths after cutover (machine-wide no-backward-compat policy). Old skill dir is deleted in the cutover batch.
- **External consumer checklist (verified 2026-06-11 by tracing live configs):**
  1. launchd `com.dobby.dream-memory.plist` → absolute path `skills-source/owned/dobby-lifecycle/scripts/dream-memory`.
  2. dobby-dashboard `server/workspaceApi.ts` — `DOBBY_DASHBOARD_SESSION_START_HOOK` default → `.../dobby-lifecycle/scripts/hooks/session-start`; also docs in `docs/architecture/system-overview.md`.
  3. Workspace thin wrappers in adi + angie `scripts/hooks/{session_start,user_prompt_submit,finalize_codex_thread,finalize_claude_session}.py` → delegate via `.agents/skills/dobby-lifecycle` symlink.
  4. `dobby-workspace/scripts/validate` orchestrator → routes session files to `dobby-lifecycle/scripts/validate` (becomes internal after merge).
  5. `agents/codex/scripts/finalize-*.py` + `archive-stale-claude-sessions.py` — verify how they resolve repo hooks / skill scripts; repoint if they name dobby-lifecycle.
  6. Generated symlinks `.agents/skills/dobby-lifecycle` + `.claude/skills/dobby-lifecycle` in ALL managed repos → regenerate via bootstrap after the move.
  7. Docs/references: body-map.md, dobby-lifecycle SKILL.md cross-references from other skills (`dobby-workspace`, `dobby-shelf`?), dashboard docs, lifecycle-hooks.md.
  8. Skill triggers: any prompt/docs telling agents to "use the dobby-lifecycle skill".
- **Stale path aliases found while tracing (fix in passing):**
  - codexclaw `mobile-gateway/.env.example` references `/Users/dobby/.agents/codex/scripts/finalize-codex-thread.py` — `~/.agents/codex/` does not exist (only `hooks`, `skills`). Point the example at the real default.
  - adi/angie `scripts/hooks/session_start.py` docstrings reference `~/.agents/hooks/scripts/...` while generated configs use `$HOME/GitHub/agents/hooks/scripts/...` — standardize on the real path in docstrings.

## Done When
- [ ] `skills-source/owned/dobby-lifecycle/` no longer exists; all contents live under `dobby-workspace/`.
- [ ] All 8 consumer classes repointed; `grep -r dobby-lifecycle` across `~/GitHub/agents`, adi, angie, dobby-dashboard, codexclaw, `~/Library/LaunchAgents` returns only archives/history.
- [ ] Surfaces regenerated in all managed repos; launchd dream-memory job reloaded and fires.
- [ ] Boot + finalize smoke: fresh session boots in both workspaces; one real finalize writes a v4 record; dashboard boot view renders.
- [ ] Stale `~/.agents` aliases fixed (gateway env example, wrapper docstrings).
- [ ] Merged SKILL.md reads as one skill; tests green (`dobby-workspace/tests/run.sh` covering former lifecycle tests).

## Milestones
- [ ] M1 — File move + internal wiring (scripts/prompts/references/tests merged; validate orchestrator internalized). Validate: skill tests green.
- [ ] M2 — External repoint (checklist items 1–8) + surface regeneration + launchd reload. Validate: global grep clean; dream job `launchctl kickstart` runs.
- [ ] M3 — Smoke + docs (boot both workspaces, finalize one real session, dashboard check; merged SKILL.md; alias fixes). Validate: evidence in progress log; archive tracker.

## Execution Rules
- One batch per milestone; never leave a state where a launchd job or runtime hook points at a missing path overnight.
- Edit canonical sources here; regenerate workspace surfaces — never hand-edit symlinked/generated files.
- Update this tracker before ending each run.
- Archive to `docs/projects/archive/merge-dobby-workspace-lifecycle/` when Done When holds.

## Decisions
- Survivor name `dobby-workspace`: "the skill that runs a Dobby workspace — its shape and its rhythms." More external callers point at lifecycle paths, so the rename burden was equal either way; the honest name won.
- Internal layout after merge: keep `scripts/hooks/`, `scripts/` CLIs, `prompts/`, `references/` flat under dobby-workspace (no `lifecycle/` subfolder — the point is one module).

## Open Questions / Blockers
- None.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| todo | M1: move files + internal wiring + merged tests | parent |  |

## Backlog / Remaining Work
- [ ] M2: external repoint per checklist + regenerate surfaces + launchd reload.
- [ ] M3: smoke (boot ×2, finalize ×1, dashboard), merged SKILL.md, alias fixes, global grep proof, archive.

## Validation / Test Plan
- `dobby-workspace/tests/run.sh` (absorbing lifecycle tests); `~/GitHub/agents/scripts/check-fast.sh`.
- `grep -rn dobby-lifecycle` across agents, adi, angie, dobby-dashboard, codexclaw, LaunchAgents → only historical/archive hits.
- Boot: `AGENT_REPO_ROOT=<ws> .../dobby-workspace/scripts/hooks/session-start` for adi and angie.
- `launchctl kickstart -k gui/$(id -u)/com.dobby.dream-memory` after plist update.
- Dashboard `npm run check-fast` + Boot view renders.

## Progress Log
- 2026-06-11: [IN-PROGRESS] Tracker created with verified consumer checklist (traced launchd plists, gateway env, generated hook configs, dashboard defaults, workspace wrappers). Execution intentionally deferred to a fresh session — touches live machinery (launchd, runtime hooks).
