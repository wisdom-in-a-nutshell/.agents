# Morning

Use for day-start orientation.

Required fields:

- `sleep.score_10`
- `energy.score_10`
- `mood.score_10`
- `grateful` with 3 items
- `one_thing_that_matters`

Optional fields:

- `sleep.notes`
- `energy.notes`
- `mood.notes`
- `show_up_as`
- `implementation_next_step`
- `dobby_follow_up`
- `raw_input`

Prompt:

1. Sleep, energy, and mood out of 10 — plus any quick notes for any of them if useful.
2. Three things you're grateful for?
3. What is the one thing that matters today?
4. What is the smallest concrete next action for that thing?
5. Optional: how do you want to show up?

Implementation bridge:

- Treat `one_thing_that_matters` as orientation, not execution.
- Capture the smallest concrete next action as `implementation_next_step` when the user provides one or it can be inferred cleanly.
- If the next action is a real personal open loop, offer to add it to Shelf or update an existing Shelf item after saving the check-in. Do not create Shelf items from vague intentions.
- If Dobby should actively follow up later, capture that as `dobby_follow_up` and convert it to Shelf only when it is a concrete user-facing reminder/action.

Schema:

```json
{
  "agent": "workspace-slug",
  "date": "YYYY-MM-DD",
  "kind": "morning",
  "tz": "Europe/Berlin",
  "captured_at": "ISO-8601 timestamp",
  "source": "chat:text",
  "sleep": {
    "score_10": 7,
    "notes": "Slept mostly well, but waking up felt heavy."
  },
  "energy": {
    "score_10": 6,
    "notes": "Energy improved after coffee."
  },
  "mood": {
    "score_10": 7,
    "notes": "Mood is fine but a bit fragile after last night."
  },
  "grateful": ["...", "...", "..."],
  "one_thing_that_matters": "...",
  "implementation_next_step": "...",
  "show_up_as": "...",
  "dobby_follow_up": "...",
  "raw_input": "optional"
}
```

Follow-up rule:

- If the user gives a rough paragraph, extract the three state scores, any useful notes, gratitude items, and priority first.
- Keep `sleep.notes`, `energy.notes`, and `mood.notes` short and factual. They can be reasons, symptoms, or quick qualitative summaries.
- Infer notes only when the raw text clearly supports them. If not, omit them.
- Do not ask a follow-up just to fill notes.
- Ask only for any missing required field.
- For implementation, prefer one tiny next action over a plan. If unclear, ask: "What's the smallest concrete next action?"
