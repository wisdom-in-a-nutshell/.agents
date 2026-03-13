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
- `win_if`
- `show_up_as`
- `raw_input`

Prompt:

1. Sleep, energy, and mood out of 10 — plus any quick notes for any of them if useful.
2. Three things you're grateful for?
3. What is the one thing that matters today?
4. Optional: if today goes well, what will be true?
5. Optional: how do you want to show up?

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
  "win_if": "...",
  "show_up_as": "...",
  "raw_input": "optional"
}
```

Follow-up rule:

- If the user gives a rough paragraph, extract the three state scores, any useful notes, gratitude items, and priority first.
- Keep `sleep.notes`, `energy.notes`, and `mood.notes` short and factual. They can be reasons, symptoms, or quick qualitative summaries.
- Infer notes only when the raw text clearly supports them. If not, omit them.
- Do not ask a follow-up just to fill notes.
- Ask only for any missing required field.
