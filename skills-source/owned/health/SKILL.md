---
name: health
description: Read, refresh, and query repo-local personal health data. Use when answering questions about sleep, weight, body composition, activity, workouts, devices, or recent health trends, and when syncing fresh health data into `reference/health/` from the canonical health snapshot API.
---

# Health

## Overview
Use this skill for personal health work in the local memory-bank flow.

Important boundary:

- The canonical read surface is the local sink under `reference/health/`.
- The skill pulls from a normalized health snapshot API.
- Upstream systems own provider auth, token refresh, and normalization.
- The skill only fetches the normalized snapshot JSON and writes the local sink.
- The skill is portable across repos; by default it writes to `reference/health/` under the current repo root.
- The query tooling in this skill exists mainly for Dobby, not as a user-facing product surface.

## Default Workflow

1. Identify whether the user wants a read, a refresh, or both.
2. For common health questions, prefer the local query script over manual JSON inspection.
3. Only run a sync when the user asks for refresh/current data or when the sink is clearly stale for the question.
4. After syncing, re-read the sink or rerun the local query script instead of reasoning from raw API payloads.
5. If Adi asks a recurring health question that is awkward to answer with the current query script, answer it as best you can from the sink, then strongly consider improving `scripts/query_health.py` and this skill in the same run.

## Read Path

For common questions, use:

- `python3 .agents/skills/health/scripts/query_health.py --help`
- `python3 .agents/skills/health/scripts/query_health.py weight latest --json`
- `python3 .agents/skills/health/scripts/query_health.py weight avg --days 7 --json`
- `python3 .agents/skills/health/scripts/query_health.py sleep latest --json`
- `python3 .agents/skills/health/scripts/query_health.py sleep range --days 7 --json`
- `python3 .agents/skills/health/scripts/query_health.py activity today --json`
- `python3 .agents/skills/health/scripts/query_health.py activity workouts --days 7 --json`
- `python3 .agents/skills/health/scripts/query_health.py summary recent --days 7 --json`

Use the script for questions like:

- how did I sleep today / this week
- what is my weight today / average weight this week
- did I do any activities today
- did I work out this week
- how am I doing lately

Read the local files directly when:

- the question is unusual or not covered by the query script yet
- you need to debug the sink shape
- you need raw fields that the query script intentionally omits

- `reference/health/metrics/weight/latest.json`
- `reference/health/metrics/body-composition/latest.json`
- `reference/health/metrics/activity/daily/latest.json`
- `reference/health/metrics/activity/workouts/latest.json`
- `reference/health/metrics/sleep/stages/latest.json`
- `reference/health/metrics/devices/latest.json`

History lives under `reference/health/metrics/**/by-date/YYYY/YYYY-MM-DD.json`.

Current sleep rule:

- `metrics/sleep/stages/` is the useful sleep dataset.
- `metrics/sleep/summary/` currently stays empty for this account/source and should not be treated as the primary sleep source.

## Refresh Path

Canonical command:

```bash
python3 .agents/skills/health/scripts/sync_health.py
```

Useful variants:

```bash
python3 .agents/skills/health/scripts/sync_health.py --json
python3 .agents/skills/health/scripts/sync_health.py --output-root /tmp/health-sink
python3 .agents/skills/health/scripts/sync_health.py --days-back 3
```

Current defaults:

- API URL:
  - the hardcoded canonical deployed health snapshot URL in `scripts/sync_health.py`
- sink root:
  - `reference/health/` under the current repo root
- recent sync window: 2 days for measurements, activity, workouts, and sleep

Path behavior:

- Nothing is hard-coded to `adi`.
- Running the script inside another repo writes to that repo's `reference/health/` by default.
- Use `--output-root` when the sink should live somewhere else.
- The default person selector is the current repo root name, overridden by `--person` only when needed.

Current person/account boundary:

- The current snapshot endpoint supports the person keys `adi` and `angie`.
- The skill passes the repo root name as the default person key, so `adi` maps to Adi and `angie` maps to Angie.
- Keep separate sink roots per person or per repo; do not mix multiple people into one `reference/health/`.

## Implementation Notes

- The skill should stay thin.
- Do not duplicate provider auth or token logic here.
- Extend the upstream snapshot endpoint when new health domains are needed, then keep this skill as a simple local writer.
- Treat `scripts/query_health.py` as an internal Dobby helper that should evolve with repeated real usage.
- Dobby has standing permission to improve the local query surface directly when Adi's real questions expose friction or repetition; no extra permission is needed for those internal skill improvements.
- When Adi asks a health question that feels likely to recur, prefer improving the local query surface instead of repeatedly doing ad hoc JSON inspection by hand.
- Prefer additive improvements: add or refine deterministic subcommands, fields, and summaries rather than replacing the whole interface.
- When evolving the query surface, validate against the real local sink and update the skill docs in the same change so future runs inherit the improvement.

## Resources

- `references/data-model.md` - current sink layout and reading rules.
- `scripts/sync_health.py` - canonical sync entrypoint for this skill.
- `scripts/query_health.py` - canonical local query/read entrypoint for common health questions.
