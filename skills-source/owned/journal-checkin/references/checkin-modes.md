# Check-In Modes

## Morning

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
  "agent": "profile-slug",
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

## Evening

Use for a late-day reset before the day is fully closed.

Required fields:

- `mood_10`
- `energy_10`
- `what_moved_today`
- `what_feels_unresolved`
- `what_still_matters_tonight`
- `boundary_for_tonight`

Optional fields:

- `raw_input`

Prompt:

1. Mood and energy right now out of 10?
2. What actually moved today?
3. What feels unresolved or noisy?
4. What still matters tonight?
5. What boundary would make tonight feel clean?

Schema:

```json
{
  "agent": "profile-slug",
  "date": "YYYY-MM-DD",
  "kind": "evening",
  "tz": "Europe/Berlin",
  "updated_at": "ISO-8601 timestamp",
  "source": "chat:text",
  "mood_10": 7,
  "energy_10": 6,
  "what_moved_today": "...",
  "what_feels_unresolved": "...",
  "what_still_matters_tonight": "...",
  "boundary_for_tonight": "...",
  "raw_input": "optional"
}
```

## Night

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
  "agent": "profile-slug",
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

## General

Use for flexible, non-time-bound journaling, partial reflections, or when the active profile user wants to dump thoughts and have them saved cleanly.

Required fields:

- `summary`

Optional fields:

- `mood_10`
- `energy_10`
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
  "agent": "profile-slug",
  "date": "YYYY-MM-DD",
  "kind": "general",
  "tz": "Europe/Berlin",
  "updated_at": "ISO-8601 timestamp",
  "source": "chat:text",
  "summary": "...",
  "what_feels_present": "...",
  "what_matters_now": "...",
  "next_step": "...",
  "tags": ["..."],
  "raw_input": "optional"
}
```

File naming:

- `morning.json`
- `evening.json`
- `night.json`
- `general-HHMMSS.json`

## Follow-Up Rule

If the initial answer is incomplete:

1. Extract everything already present.
2. List only the missing required fields.
3. Ask for those missing fields directly.
4. Save once the mode is complete, unless Adi explicitly wants a rough partial capture.
