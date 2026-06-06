You are running the final memory-preservation turn in this Codex thread before it is archived.

Remember this session for continuity. This is a loss-prevention checkpoint for one ending thread, not a broad cross-session dreaming pass.

## Runtime context

```json
{
  "workspaceRoot": {{workspace_root_json}},
  "sourceThreadId": {{thread_id_json}},
  "finalizationTrigger": {{trigger_json}},
  "bodyMapPath": {{body_map_path_json}},
  "sessionMemoryClient": {{session_memory_cli_json}}
}
```

## Core task

1. Read `{{body_map_path}}` for the Dobby workspace routing contract.
2. Audit this thread for useful continuity that may not already have been preserved. Adi should not have to remember to say “update memory” while chatting.
3. Capture only what would make a future continuation worse if lost. Do not summarize the whole conversation.
4. Prefer one compact session-memory JSON record. If nothing materially useful changed, write nothing.
5. Promote to durable files only when the destination is obvious from the body map and the update is genuinely useful now.
6. Do not archive, delete, compact, or otherwise manage this thread. The external finalizer archives after this turn succeeds.

## What to look for

Look for practical carry-forward items from this thread:

- decisions Adi made or approved
- explicit preferences, corrections, or “do this differently next time” instructions
- commitments, blockers, or follow-up context
- project state or a resume point that future agents need
- durable facts about Adi, Angie/family, health, work, finances, or Dobby’s operating style
- assistant promises such as “I’ll remember/add/update/track this” that were not actually written
- a compact synthesis from this session itself when the thread was reflective/therapeutic/strategic and the synthesis would materially improve future support

Avoid generic topic summaries, transcript-like detail, noisy implementation chatter, or facts already captured elsewhere.

## Routing rules

Default to session memory. Promote outside session memory only when clear:

- `memory/sessions/YYYY/MM/DD-HHMMSS.json` — default continuity index card for this ending thread.
- `state/shelf.json` via the Shelf client — personal actionable open loops, purchases, habits, waiting items, or commitments from Adi.
- project tracker under `projects/<project>/tasks.md` — Dobby/system/project work state, decisions, resume points, and open implementation questions.
- `memory/now.json` — this week’s active orientation only; do not use it as a generic session summary.
- `memory/areas/<area>/log.jsonl` — concrete dated area facts/events.
- `memory/areas/<area>/canon.json` — durable area understanding after the fact is stable enough.
- `dobby/constitution.json` or `memory/profile.json` — rare durable identity, value, boundary, or support-pattern changes. Use only when the session clearly establishes a stable truth or an explicit instruction about how Dobby should serve Adi.
- shared `dobby-workspace` body map / linter — only when the session explicitly changed workspace shape or routing rules. Do not invent a new location just because routing feels imperfect.

Before any non-session-memory write, read the target file first and avoid duplicating existing content. If routing is unclear, preserve the candidate in session memory instead of scattering it.

## Session-memory write shape

Use the session-memory client for the compact JSON record:

```bash
cat <<'JSON' | {{session_memory_cli_shell}} write --stdin-json --no-input
{
  "threadId": {{thread_id_json}},
  "trigger": {{trigger_json}},
  "title": "Short dashboard/index label",
  "summary": "Curated Markdown continuity index: what matters from this thread, not a transcript recap.",
  "workspaceChanges": "Plain-English Markdown note about durable workspace changes made during consolidation, excluding this session-memory file. If none: No durable workspace changes besides this session-memory record."
}
JSON
```

If unsure about the current record contract, run `{{session_memory_cli_shell}} schema --no-input` before writing.

The session-memory client is the schema source of truth and validates the record.

Quality bar for `title`:

- Short enough for a dashboard row.
- Name the memory, not the trigger.
- Prefer concrete labels like `Morning check-in captured`, `Dashboard schema cleanup`, or `Co-founder boundary clarified`.

Quality bar for `summary`:

- Treat it as a continuity index card, not a transcript recap.
- Use Markdown when bullets make it clearer.
- Include what matters, why it matters, and enough context to decide whether the full thread should be reopened via `threadId`.
- Prefer decisions, commitments, corrections, and continuation points.
- Do not write “We discussed X” unless the actual carry-forward point is clear.
- If this thread already has a session record for the same `threadId`, write only a real delta or no new record.

Quality bar for `workspaceChanges`:

- Plain English / Markdown for human visibility.
- Report durable workspace or memory changes made during this finalization turn, excluding the session-memory record itself.
- If no durable files or structured memory were changed, write: `No durable workspace changes besides this session-memory record.`
- Do not include full diffs or reconstruct unrelated git history.

## Boundaries

This turn may synthesize within the current thread when useful, especially after long reflective, therapeutic, strategic, or design conversations. But do not perform cross-session pattern mining, memory pruning, broad deduplication, or life-level reinterpretation from weak signals. Those belong to the separate future dreaming process.

Preserve sensitive material minimally: capture the practical implication, not raw intimate detail, secrets, account numbers, or unnecessary private content.

## Final reply

When finished, reply briefly with:

- memory/session path changed, if any
- durable file(s) changed, if any
- or “No memory changes needed”
