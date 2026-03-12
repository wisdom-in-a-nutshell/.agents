# Morning

Use for day-start orientation.

Required fields:

- `sleep.score_10`
- `energy_10`
- `mood_10`
- `grateful` with 3 items
- `one_thing_that_matters`

Optional fields:

- `sleep.notes`
- `win_if`
- `show_up_as`
- `raw_input`

Prompt:

1. Sleep score out of 10, and any note on how it was or what affected it?
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
  "updated_at": "ISO-8601 timestamp",
  "source": "chat:text",
  "sleep": {
    "score_10": 7,
    "notes": "Slept mostly well, but waking up felt heavy."
  },
  "energy_10": 6,
  "mood_10": 7,
  "grateful": ["...", "...", "..."],
  "one_thing_that_matters": "...",
  "win_if": "...",
  "show_up_as": "...",
  "raw_input": "optional"
}
```

Follow-up rule:

- If the user gives a rough paragraph, extract the sleep score, any sleep note, the other scores, gratitude items, and priority first.
- Keep `sleep.notes` short and factual. It can be a reason, a symptom, or a quick qualitative summary.
- Ask only for any missing required field.
