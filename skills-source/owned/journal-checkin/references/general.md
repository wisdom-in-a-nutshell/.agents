# General

Use for flexible, non-time-bound journaling, partial reflections, or when the user wants to dump thoughts and have them saved cleanly.

Required fields:

- `summary`

Optional fields:

- `mood.score_10`
- `mood.notes`
- `energy.score_10`
- `energy.notes`
- `what_feels_present`
- `what_matters_now`
- `next_step`
- `tags`
- `raw_input`

Prompt:

1. What is going on?
2. What feels most important or most charged?
3. What matters now?
4. Optional: is there a next step or decision to capture?

Schema:

```json
{
  "agent": "workspace-slug",
  "date": "YYYY-MM-DD",
  "kind": "general",
  "tz": "Europe/Berlin",
  "updated_at": "ISO-8601 timestamp",
  "source": "chat:text",
  "mood": {
    "score_10": 6,
    "notes": "Mood is unsettled."
  },
  "energy": {
    "score_10": 5,
    "notes": "Energy is flat."
  },
  "summary": "...",
  "what_feels_present": "...",
  "what_matters_now": "...",
  "next_step": "...",
  "tags": ["..."],
  "raw_input": "optional"
}
```

File naming:

- `general-HHMMSS.json`

Follow-up rule:

- Capture structure from the user's own format when possible.
- Infer `mood.notes` and `energy.notes` only when the raw text clearly supports them. If not, omit them.
- Only ask a follow-up if the summary or the key point is not clear enough to save.
