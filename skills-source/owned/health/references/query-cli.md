# Health Query CLI

Use this file when the health question is common enough to route through the
local query CLI instead of manual JSON inspection.

Canonical entrypoint:

```bash
python3 .agents/skills/health/scripts/query_health.py --help
```

## Common commands

### Stable profile facts

```bash
python3 .agents/skills/health/scripts/query_health.py profile latest --json
python3 .agents/skills/health/scripts/query_health.py profile height --human
```

### Weight

```bash
python3 .agents/skills/health/scripts/query_health.py weight latest --json
python3 .agents/skills/health/scripts/query_health.py weight avg --days 7 --json
```

### Sleep

```bash
python3 .agents/skills/health/scripts/query_health.py sleep latest --json
python3 .agents/skills/health/scripts/query_health.py sleep range --days 7 --json
```

### Activity and workouts

```bash
python3 .agents/skills/health/scripts/query_health.py activity today --json
python3 .agents/skills/health/scripts/query_health.py activity date --date 2026-03-23 --json
python3 .agents/skills/health/scripts/query_health.py activity workouts --days 7 --json
```

### Lightweight recent summary

```bash
python3 .agents/skills/health/scripts/query_health.py summary recent --days 7 --json
```


## Presentation Default

For user-facing answers built from this CLI:

- Prefer minimal markdown tables when returning multiple health metrics or recent rows.
- Keep the table compact and omit non-essential columns.
- For recent same-year rows, prefer short dates like `03-23` instead of repeating the full year.
- This is a soft default; switch to prose when the question is better served by a short direct answer.

## Output modes

- `--json` for machine-readable output
- `--human` for concise direct answers
- `--plain` for stable `key=value` output

If no mode is passed:

- TTY stdout -> human mode
- non-TTY stdout -> JSON mode

## Use this CLI for

- how did I sleep today / this week
- what is my weight today / average this week
- did I do any activities today
- did I work out last week
- how many kilometers did I run last week
- what is my stored height
- how am I doing lately

## Fall back to raw files when

- the question is unusual or debugging-oriented
- the CLI does not expose the needed field yet
- you are checking the sink shape itself
