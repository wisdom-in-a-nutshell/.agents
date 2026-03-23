# Health Sink Data Model

Canonical sink root:

- `reference/health/`

Primary split:

- `metrics/` for recurring structured JSON data
- `records/` for documents and irregular artifacts

Current recurring metric datasets:

- `metrics/weight/`
- `metrics/body-composition/`
- `metrics/activity/daily/`
- `metrics/activity/workouts/`
- `metrics/sleep/stages/`
- `metrics/sleep/summary/`
- `metrics/devices/`

History pattern:

- `latest.json` is the fast current read path.
- `by-date/YYYY/YYYY-MM-DD.json` is the durable history path.

Reading defaults:

1. Read `latest.json` first.
2. Only inspect `by-date/` when the user wants trend/history.
3. Treat `weight/` and `body-composition/` as separate datasets.
4. Treat `metrics/sleep/stages/` as the real sleep source today.
5. Do not rely on `metrics/sleep/summary/` unless it actually contains rows; Withings currently returns empty summary results for this account/source.

Current upstream implementation:

- Withings is the only implemented provider.
- Current fetch path is the `win` snapshot endpoint, not a direct provider call from the skill.
- `HEALTH_REFERENCE_ROOT` can override the sink root when the health store lives outside the current repo root.
- Without `HEALTH_REFERENCE_ROOT`, the script writes to `reference/health/` under the current repo root it is invoked from.
- The default person selector is the current repo root name, overridden by `HEALTH_PERSON` or `--person`.
- The current snapshot endpoint supports `adi` and `angie`; keep separate sink roots or separate repos per person.
