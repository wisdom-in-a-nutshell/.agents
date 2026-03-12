# Night

Use for end-of-day closure and tomorrow carry-forward.

Required fields:

- `mood_10`
- `energy_10`
- `went_well`
- `could_have_been_improved`
- `actions_to_improve_tomorrow`

Optional fields:

- `raw_input`

Prompt:

1. Mood and energy out of 10?
2. What went well today?
3. What could have been improved?
4. What is one action to improve tomorrow?

Schema:

```json
{
  "agent": "workspace-slug",
  "date": "YYYY-MM-DD",
  "kind": "night",
  "tz": "Europe/Berlin",
  "updated_at": "ISO-8601 timestamp",
  "source": "chat:text",
  "mood_10": 7,
  "energy_10": 6,
  "went_well": "...",
  "could_have_been_improved": "...",
  "actions_to_improve_tomorrow": "...",
  "raw_input": "optional"
}
```

Follow-up rule:

- If the user gives a freeform end-of-day summary, extract these four parts first.
- Ask only for whichever required field is still missing.
