---
name: health
description: Read or refresh the personal health sink. Use when answering questions about sleep, activity, workouts, weight, body composition, devices, or when syncing fresh health data into `reference/health/`.
---

# Health

## Overview
Use this skill for personal health work in the local memory-bank flow.

Important boundary:

- The canonical read surface is the local sink under `reference/health/`.
- The current upstream source is Withings.
- `win` owns Withings auth, token refresh, and upstream normalization.
- The skill only fetches the normalized snapshot JSON and writes the local sink.

## Default Workflow

1. Identify whether the user wants a read, a refresh, or both.
2. For normal health questions, read the local sink first.
3. Only run a sync when the user asks for refresh/current data or when the sink is clearly stale for the question.
4. After syncing, re-read the sink instead of reasoning from raw upstream payloads.

## Read Path

Read the local files directly:

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
  - `HEALTH_SNAPSHOT_API_URL` if set
  - otherwise the stable `win` `/personal/health/withings-snapshot` URL
- sink root:
  - `HEALTH_REFERENCE_ROOT` if set
  - otherwise `reference/health/` under the current repo root
- recent sync window: 2 days for measurements, activity, workouts, and sleep

Repo bootstrap default:

```bash
scripts/local/secrets/bootstrap_local_env_from_keyvault.sh
```

## Implementation Notes

- The skill should stay thin.
- Do not duplicate Withings auth or token logic here.
- Extend the `win` snapshot endpoint when new health domains are needed, then keep this skill as a simple local writer.

## Resources

- `references/data-model.md` - current sink layout and reading rules.
- `scripts/sync_health.py` - canonical sync entrypoint for this skill.
