# General

Use for flexible, non-time-bound journaling, partial reflections, or when the user wants to dump thoughts and have them saved cleanly.

Required fields:

- `title` — short handle, 1–7 words
- `summary`
- `body` — full capture, Markdown string
- `body_format` — always `markdown`

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
  "captured_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "schema_version": 1,
  "entries": [
    {
      "id": "stable-entry-id",
      "title": "Short handle",
      "summary": "Compact preview. Maximum three sentences and 45 words.",
      "body": "## Markdown body\n\nFull preserved note.",
      "body_format": "markdown",
      "tags": ["..."],
      "raw_input": "optional",
      "captured_at": "ISO-8601 timestamp",
      "mood": {
        "score_10": 6,
        "notes": "Mood is unsettled."
      },
      "energy": {
        "score_10": 5,
        "notes": "Energy is flat."
      },
      "what_feels_present": "...",
      "what_matters_now": "...",
      "next_step": "..."
    }
  ]
}
```

File naming:

- `general.json`
- Append multiple captures from the same day into `entries[]`.
- Do not create Markdown files under `journal/daily/`.
- Keep `body` as Markdown text inside JSON so UI can render structured notes without reintroducing Markdown files.
- Enforced limits: `title` is 1–7 words; `summary` is at most 3 sentences and 45 words; `body` is freeform Markdown.

Follow-up rule:

- Capture structure from the user's own format when possible.
- Infer `mood.notes` and `energy.notes` only when the raw text clearly supports them. If not, omit them.
- Only ask a follow-up if the summary or the key point is not clear enough to save.
