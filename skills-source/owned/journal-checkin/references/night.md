# Night

Use for end-of-day closure and tomorrow carry-forward.

Required fields:

- `mood.score_10`
- `energy.score_10`
- `went_well`
- `could_have_been_improved`
- `actions_to_improve_tomorrow`

Optional fields:

- `mood.notes`
- `energy.notes`
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
  "captured_at": "ISO-8601 timestamp",
  "source": "chat:text",
  "mood": {
    "score_10": 7,
    "notes": "Mood improved compared to the morning."
  },
  "energy": {
    "score_10": 6,
    "notes": "Energy dipped late because of no movement."
  },
  "went_well": "...",
  "could_have_been_improved": "...",
  "actions_to_improve_tomorrow": "...",
  "raw_input": "optional"
}
```

Follow-up rule:

- If the user gives a freeform end-of-day summary, extract these four parts first.
- Keep `mood.notes` and `energy.notes` short and factual when they are clearly present.
- Infer notes only when the raw text clearly supports them. If not, omit them.
- Do not ask a follow-up just to fill notes.
- Ask only for whichever required field is still missing.
