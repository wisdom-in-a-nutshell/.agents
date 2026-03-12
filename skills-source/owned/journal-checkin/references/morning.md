# Morning

Use for day-start orientation.

Required fields:

- `sleep_10`
- `energy_10`
- `mood_10`
- `grateful` with 3 items
- `one_thing_that_matters`

Optional fields:

- `win_if`
- `show_up_as`
- `raw_input`

Prompt:

1. Sleep, energy, and mood out of 10?
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
  "sleep_10": 7,
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

- If the user gives a rough paragraph, extract the scores, gratitude items, and priority first.
- Ask only for any missing required field.
