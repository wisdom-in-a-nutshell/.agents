# Merge dobby-lifecycle into dobby-workspace (+ consolidation fixes)

## Goal
One skill — `dobby-workspace` — owns both the workspace shape (body map, linter) and its lifecycle (boot, per-turn, finalize, session memory, dreaming); `dobby-lifecycle` ceases to exist, with every external caller repointed and no old paths left behind. Riding along (Adi, 2026-06-11): the session-noise gate at finalize and the body-map boot-cut slimming.

## Why / Impact
Evidence from the 2026-06-11 memory-format migration: every batch touched both skills together — the boundary is fake (anatomy vs metabolism in theory, one module in practice). The split also caused a real staleness bug (body map describing lifecycle's session contract drifted). Risk if done wrong: boot hooks, finalize jobs, or the dream job silently stop firing.

## Scope / Non-Goals
### In Scope
- Move all of `skills-source/owned/dobby-lifecycle/` (scripts, hooks, prompts, references, agents, tests) into `skills-source/owned/dobby-workspace/`.
- Repoint every external consumer (checklist below); regenerate surfaces in all managed repos; delete the old skill directory.
- Merge SKILL.md descriptions/triggers into one coherent skill doc; one tests/run.sh.
- Apply the one-home doc rule while merging: body map points to contracts, never re-describes other skills'.
- **Ride-along 1 — session-noise gate at finalize:** skip the remember turn for trivial sessions (fewer than ~3 user turns AND no workspace changes); archive the transcript without writing a session-memory record. Applies to automatic triggers (stale-cleanup, idle-expiry); an explicit user-requested finalize always remembers.
- **Ride-along 2 — body-map boot-cut:** restructure body-map.md so core idea + routing table sit at the top, add a `<!-- boot-cut -->` marker after them, and make session-start inject only what's above the marker (~600 tokens vs ~1,500 today). Everything below stays in the same file for on-demand reads — one file, one truth, no duplication. Linter requires the marker.
### Out of Scope
- Dreaming-policy changes and Shelf review (both explicitly deferred by Adi, 2026-06-11 — he has ideas, will revisit).
- Open-questions archival process (explicitly dropped by Adi: not needed).
- Session tldr short-summary + lint — already shipped in the memory-format migration (meta.json `tldr` required, ≤240 chars, lint-enforced; boot shows tldrs for older sessions). No further work.
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
- [ ] Noise gate live: a trivial automatic finalize archives without writing a session record; a real session still writes v4. Covered by a test.
- [ ] Boot-cut live: `<!-- boot-cut -->` in body-map.md; boot injects only the slice above it in both workspaces; linter fails when the marker is missing; boot token total drops accordingly in the dashboard Boot view.

## Milestones
- [ ] M1 — File move + internal wiring (scripts/prompts/references/tests merged; validate orchestrator internalized). Validate: skill tests green.
- [ ] M2 — External repoint (checklist items 1–8) + surface regeneration + launchd reload. Validate: global grep clean; dream job `launchctl kickstart` runs.
- [ ] M3 — Smoke + docs (boot both workspaces, finalize one real session, dashboard check; merged SKILL.md; alias fixes). Validate: evidence in progress log.
- [ ] M4 — Consolidation fixes on the merged skill: session-noise gate at finalize + body-map boot-cut + linter marker rule. Validate: gate test green; boot output diff shows only above-cut body map; archive tracker.

## Execution Rules
- One batch per milestone; never leave a state where a launchd job or runtime hook points at a missing path overnight.
- Edit canonical sources here; regenerate workspace surfaces — never hand-edit symlinked/generated files.
- Update this tracker before ending each run.
- Archive to `docs/projects/archive/merge-dobby-workspace-lifecycle/` when Done When holds.

## Decisions
- Survivor name `dobby-workspace`: "the skill that runs a Dobby workspace — its shape and its rhythms." More external callers point at lifecycle paths, so the rename burden was equal either way; the honest name won.
- Internal layout after merge: keep `scripts/hooks/`, `scripts/` CLIs, `prompts/`, `references/` flat under dobby-workspace (no `lifecycle/` subfolder — the point is one module).
- Body map stays (Adi delegated keep/remove to Dobby, 2026-06-11). Rationale: the routing table is load-bearing — a quick phone/gateway session writing a journal entry needs to know where content goes without loading any skill. But organ prose, validation architecture, and the memory contract are reference material; they move below the boot-cut and load on demand.
- Boot-cut mechanism over a separate boot-map file: a marker in one file keeps the routing table in exactly one place; a second compact file would duplicate it and re-create the drift that the one-home rule exists to prevent.
- Noise-gate thresholds start at "<3 user turns AND no workspace changes"; explicit finalize is exempt because a user-initiated end signals intent to remember. Tune later from real archives if good sessions get skipped.

## Open Questions / Blockers
- None.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| todo | M1: move files + internal wiring + merged tests | parent |  |

## Backlog / Remaining Work
- [ ] M2: external repoint per checklist + regenerate surfaces + launchd reload.
- [ ] M3: smoke (boot ×2, finalize ×1, dashboard), merged SKILL.md, alias fixes, global grep proof.
- [ ] M4: session-noise gate at finalize + body-map boot-cut + linter marker rule; archive tracker.

## Validation / Test Plan
- `dobby-workspace/tests/run.sh` (absorbing lifecycle tests); `~/GitHub/agents/scripts/check-fast.sh`.
- `grep -rn dobby-lifecycle` across agents, adi, angie, dobby-dashboard, codexclaw, LaunchAgents → only historical/archive hits.
- Boot: `AGENT_REPO_ROOT=<ws> .../dobby-workspace/scripts/hooks/session-start` for adi and angie.
- `launchctl kickstart -k gui/$(id -u)/com.dobby.dream-memory` after plist update.
- Dashboard `npm run check-fast` + Boot view renders.

## Progress Log
- 2026-06-11: [IN-PROGRESS] Tracker created with verified consumer checklist (traced launchd plists, gateway env, generated hook configs, dashboard defaults, workspace wrappers). Execution intentionally deferred to a fresh session — touches live machinery (launchd, runtime hooks).
- 2026-06-11: [IN-PROGRESS] Consolidated Adi's review decisions into this tracker as M4: session-noise gate at finalize (approved) and body-map boot-cut slimming (delegated to Dobby; decision recorded under Decisions). Recorded as out of scope: tldr+lint (already shipped in memory-format migration), open-questions process (dropped), Shelf review and dreaming policy (deferred, Adi has ideas).
