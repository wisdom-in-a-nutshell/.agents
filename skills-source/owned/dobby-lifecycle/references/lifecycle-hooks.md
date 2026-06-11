# Dobby lifecycle hooks

Lifecycle details live here so the shared `dobby-workspace` body map can stay
focused on workspace meaning instead of becoming a hook runbook.

## Simple lifecycle map

- `SessionStart`: read durable context and inject a compact boot packet into the
  active agent thread.
- `UserPromptSubmit`: add lightweight per-turn context when useful.
- Normal conversation/work happens in the live Codex thread.
- `finalize-codex-thread`: explicit end-of-thread command. It derives the repo
  from Codex App Server `thread/read`, runs the repo's self-contained
  finalization hook when present, and archives only after that hook succeeds.
- Next `SessionStart`: recent `memory/sessions/...` JSON summaries return
  continuity to the next thread.

Short version:

- **SessionStart is read/inject.** It gathers the current Dobby context and gives
  the agent enough memory to continue well.
- **FinalizeCodexThread is explicit same-thread finalization.** The global
  `finalize-codex-thread` command is the public primitive. It runs repo policy
  from `scripts/hooks/finalize_codex_thread.py` when present.
- **Dobby finalization is self-contained.** The repo hook runs
  `remember-session`, which starts one final same-thread Codex turn using the
  versioned prompt at `prompts/remember-session.md`. That turn uses the
  `session-memory` client for session continuity and decides whether anything
  should also be written under `memory/now.md`, an area canon/log, `dobby/constitution.md` or `memory/profile.md`, Shelf,
  or a project tracker by reading the shared `dobby-workspace` body map.
- **Archive is conditional.** If the repo hook, remember-session turn, or
  archive request fails, the source thread is left unarchived so stale cleanup
  can retry later.
- **`memory/sessions` is the bridge.** End-of-thread JSON summaries become part
  of the next boot context.
- **`memory/now.md`, area canon/log, `dobby/constitution.md`, and `memory/profile.md` are promotion targets only.** They
  should be updated when something durable changes, not for every session.

## Finalization boundary rule

Across finalization layers, pass only:

- `thread_id`: the canonical identifier for the Codex thread.
- `reason`: optional context for why finalization is running.

Do not pass `cwd`, `repo_root`, `source`, thread metadata, timeout config, Codex
binary config, archive flags, or prompt text across finalization boundaries.
Each layer derives what it needs from `thread_id`, and runtime tuning stays local
to the command that uses it.

## Boot

Boot context is delivered by the repo's `SessionStart` hook
(`scripts/hooks/session_start.py`), which delegates to the skill-bundled hook.
The hook reads the shared `dobby-workspace` body map and `now.md`, walks
`memory/areas/`, reads recent session-memory JSON, calls `dobby-shelf snapshot
--mode boot --plain` for the curated Shelf decision surface, and calls the
`dobby-calendar` skill CLI for upcoming events.

What boot context should include:

1. `dobby/constitution.md` or `memory/profile.md` / identity context through the runtime system-prompt mechanism.
2. Shared `dobby-workspace/references/body-map.md` as the common Dobby body map.
3. `memory/now.md`.
4. Recent session-memory summaries: last 3 plus records from the last 7 days,
   capped at 10.
5. Last dream: newest complete dream-memory run within 7 days — run id, window,
   applied/needs-Adi counts, and the report's "Next actions" (capped at 2200
   chars; changes are self-applied within bounds, one revertible commit each).
6. Shelf snapshot.
7. Calendar snapshot for the next 2 days.
8. Area manifest.

Operational limits:

- folder format: `memory/sessions/YYYY/MM/DD-HHMMSS/` with numeric suffixes on
  collision
- shared body-map boot cap: 12000 chars
- boot context: last 3 records plus records from the last 7 days, capped at 10
- Shelf boot context: `dobby-shelf snapshot --mode boot --plain`
- per-record boot cap: 2500 chars
- total recent-session boot block cap: 12000 chars

## Session memory

Session continuity lives in `memory/sessions/YYYY/MM/DD-HHMMSS/` folders, not in
`memory/now.md`. Each finalized session is one folder (schema v4):

- `meta.json` — machine facts: `schemaVersion`, `createdAt`, `threadId`,
  `runtime` (`codex`/`claude`, required), `trigger`, optional `cwd`.
- `summary.md` — the prose record: `# <title>`, the Markdown continuity index,
  then a final `## Workspace changes` section.
- `raw.jsonl` — the untouched runtime transcript, copied at finalize time
  (source of truth; runtimes delete their own copies).
- `dialogue.md` — normalized human↔agent transcript rendered from `raw.jsonl`
  by `session-transcript` (header carries the normalizer version; re-render
  any time from raw).

`raw.jsonl`/`dialogue.md` may be absent on sessions whose raw transcript was
already deleted before capture existed. The contract is code-backed by:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/session-memory schema
```

`title` is for dashboard scanning. `summary` is the curated continuity index
loaded at boot. `threadId` points back to the original transcript when deeper
retrieval is needed (a Codex thread id or a Claude session id).
`workspaceChanges` is for visibility into durable writes made during
finalization; if none happened, say so plainly. Durable decisions still get
promoted to `now.md`, area canon, or `dobby/constitution.md` or
`memory/profile.md` as appropriate.

Current trigger vocabulary:

- `codexclaw-idle-expiry` — CodexClaw finalized an idle mapped thread.
- `codexclaw-chat-end` — CodexClaw finalized a thread after explicit chat end.
- `stale-cleanup` — global `~/GitHub/agents` stale Codex thread finalizer archived an old thread.
- `manual` — direct/manual finalization or repair from a Dobby workspace.
- `migration` — legacy imported session records only; do not use for new writes.

Use the client instead of hand-writing records:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/session-memory write \
  --workspace-root /path/to/dobby-workspace \
  --trigger manual \
  --thread-id <codex-thread-id> \
  --runtime codex \
  --title "Short dashboard label" \
  --summary "Curated continuity index." \
  --workspace-changes "No durable workspace changes besides this session-memory record." \
  --no-input
```

## FinalizeCodexThread primitive

The global Codex control-plane finalizer is the preferred end-of-thread entry:

```bash
$HOME/GitHub/agents/codex/scripts/finalize-codex-thread.py \
  --thread-id <codex-thread-id> \
  --apply
```

Callers should pass only the thread id plus a reason label when useful. The
command uses `thread/read` as the source of truth for the current working
directory and repo root.

When a repo provides `scripts/hooks/finalize_codex_thread.py`, the finalizer runs
that script first. The script is self-contained repo policy: it should do any
repo-specific before-archive work itself and exit non-zero on failure. The global
finalizer deliberately sends a minimal hook payload only:

```json
{
  "schema_version": "1.0",
  "hook_event_name": "FinalizeCodexThread",
  "thread_id": "019e...",
  "reason": "manual"
}
```

The repo hook runs with `cwd` set to the repo root. It should perform its own
lookups from `thread_id` instead of relying on duplicated cwd, repo, timeout,
Codex binary, archive-mode, or thread-metadata fields from the dispatcher. The
global finalizer then:

1. archives the source thread through `thread/archive` only after repo hook
   success;
2. skips repo-specific work and archives directly when no repo hook exists;
3. leaves the source thread unarchived when the repo hook or archive request
   fails.

If the repo hook has already succeeded and App Server reports
`no rollout found for thread id` during archive, the finalizer treats that as a
nonfatal `archive_unavailable` result. The useful memory-preservation work has
already completed, and retrying the same stale thread would only create
duplicate finalization turns.

In Dobby workspaces the repo wrapper delegates to:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/hooks/finalize-codex-thread
```

That hook runs the Dobby memory-preservation behavior with the
source thread id and finalization trigger:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/remember-session \
  --thread-id <codex-thread-id> \
  --trigger manual \
  --no-input
```

`remember-session` starts one final same-thread Codex turn and asks the agent to
carry forward only useful memory. The agent-facing instruction lives in
[`prompts/remember-session.md`](/Users/dobby/GitHub/agents/skills-source/owned/dobby-lifecycle/prompts/remember-session.md),
not inline in the Python runner. The runner performs its own
`thread/read(thread_id)`, derives the repo root from the thread cwd, renders the
prompt with strict placeholders, and starts the final turn with that cwd. It
does not infer trigger semantics from label prefixes. The final turn may call
`session-memory` to write the `memory/sessions/YYYY/MM/DD-HHMMSS/` folder; it
may also make clearly routed durable updates when the body map says so. After
the remember turn succeeds, the hook runs `session-transcript capture` to copy
the raw runtime transcript into the session folder (`raw.jsonl`) and render the
normalized `dialogue.md` — best-effort: a capture failure warns but never fails
the finalization. The repo hook does not archive; the global finalizer owns
archive after the hook succeeds (the transcript locator also searches
`~/.codex/archived_sessions/`, so capture works on both sides of the archive).

Do not put Dobby memory synthesis directly in the shared `~/GitHub/agents` dispatcher.
The dispatcher routes lifecycle events; this skill owns Dobby-specific behavior.

## FinalizeClaudeSession primitive (Claude runtime twin)

Claude Code sessions get the same ending pipeline through the twin primitive:

```bash
$HOME/GitHub/agents/codex/scripts/finalize-claude-session.py \
  --session-id <claude-session-id> \
  --apply
```

Differences from the Codex flow, by construction:

- The workspace is derived from the session transcript under
  `~/.claude/projects/<munged-cwd>/<session-id>.jsonl` (there is no App Server to
  ask). Empty/cwd-less transcripts are marked finalized with nothing to remember.
- The repo hook is `scripts/hooks/finalize_claude_session.py`, which in Dobby
  workspaces delegates to `scripts/hooks/finalize-claude-session` in this skill,
  which runs `remember-claude-session`. That runner resumes the ending session
  headless (`claude -p --resume <id> --permission-mode bypassPermissions`) and
  runs the SAME versioned remember-session prompt (rendered via the shared
  `remember_lib.py` with `runtime: "claude"`), so the record is runtime-tagged.
  The hook then runs the same `session-transcript capture` step as the Codex
  twin (Claude raw transcripts are deleted by the runtime after ~30 days, so
  this copy is what makes the dialogue durable).
- There is no archive step. Instead the primitive records the session id in
  `~/.local/state/claude-control-plane/finalized-claude-sessions.json` so no
  session is ever finalized twice. Claude Desktop sidebar tidying remains the
  separate archiver's job and never touches memory.
- Live sessions are protected: ids found in `~/.claude/sessions/*.json`
  handshakes with a live pid are skipped.

Stale coverage: `finalize-stale-claude-sessions.py` (hourly LaunchAgent
`com.<user>.claude-session-finalizer`, installed by
`install-finalize-stale-claude-sessions-launchagent.sh`) scans transcript mtimes
for registered repos, 24-hour cutoff, capped per run by `--max-sessions`;
`--mark-only` absorbs a pre-existing backlog without running remember turns.
CodexClaw schedules the primitive on chat-end and 4-hour idle for Claude-owned
phone conversations, mirroring the Codex paths.

## Repo wrapper note

Dobby workspaces such as `adi` and `angie` keep repo-local files under
`scripts/hooks/` only as thin wrappers into this shared lifecycle skill.

Native Codex hook wrappers:

- `scripts/hooks/session_start.py` is reached through rendered `SessionStart`
  config in `.codex/hooks.json`.
- `scripts/hooks/user_prompt_submit.py` is reached through rendered
  `UserPromptSubmit` config in `.codex/hooks.json`.

Explicit finalization wrapper:

- `scripts/hooks/finalize_codex_thread.py` is not a native Codex hook and should
  not appear in `.codex/hooks.json`.
- It is called by the global `$HOME/GitHub/agents/codex/scripts/finalize-codex-thread.py`
  command when that command derives the repo from `thread/read` and asks the
  repo to finalize itself before archive.

Intentional non-goals for Dobby workspaces:

- no fake `SessionEnd`
- no pre-compact memory preservation
- no sidecar consolidation thread

## Dream-memory (cross-session consolidation, self-applying)

`scripts/dream-memory` is the dreaming counterpart to per-session remembering.
It gathers a deterministic inputs manifest for a review window (session folders,
journal days, `memory/now.md`, `state/shelf.json`, active project trackers,
area manifests), renders the versioned `prompts/dream-memory.md`, runs one
headless Claude turn in the workspace, and validates the run bundle written
under `memory/dreams/<run-id>/` (run id `YYYY-MM-DD-HHMM`, flat — dreams arrive
~once per night, so no year/month sharding):

- `report.md` — leads with an executive summary (`## What I changed`) Adi
  reads after the fact, then `## Needs you` for the floor/uncertain items
  (also rendered on the dashboard Dreams page)
- `run.json` — machine envelope with every candidate (categories: now,
  area_log, area_canon, soul, shelf, project, dobby_growth, stale_or_conflict,
  noop; action: applied | needs_adi | noop, applied candidates record their
  commit sha — the rollback handle)
- `inputs.manifest.json` + `events.jsonl` — runner-written audit trail

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/dream-memory \
  --workspace-root /path/to/dobby-workspace --days 7 --no-input
```

The dream applies its own changes, one git commit per candidate
(`dream(<run-id>): <candidate-id> — ...`), so rolling back one change is one
`git revert` of the sha in its candidate. A hard floor stays watchdog-enforced
by the runner: edits to `dobby/constitution.md` / `memory/profile.md` and
any file deletion are reported as violations in events + envelope (the floor
items become `needs_adi` candidates instead, approved conversationally — any
session can apply or revert on Adi's word). Shelf adds go through the
`dobby-shelf` CLI, never raw `state/shelf.json` edits. Expect benign
`workspace_changes` noise from concurrent automation (e.g. health sync)
committing mid-run. The prompt tells the dreamer to read
session `summary.md` files as the index and open `dialogue.md` selectively as
evidence, including pipeline-audit signal (tool errors, interrupted turns,
repeated corrections).

Nightly schedule: `agents/codex/scripts/install-dream-memory-launchagent.sh`
installs `com.<user>.dream-memory` (daily 05:30, 7-day window by default).
