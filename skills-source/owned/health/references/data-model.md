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

1. For common questions, prefer `scripts/query_health.py`.
2. Read `latest.json` first when inspecting raw files manually.
3. Only inspect `by-date/` when the user wants trend/history or when the query script does not cover the question yet.
4. Treat `weight/` and `body-composition/` as separate datasets.
5. Treat `metrics/sleep/stages/` as the real sleep source today.
6. Do not rely on `metrics/sleep/summary/` unless it actually contains rows; the current snapshot for this account/source may be empty.

Current upstream implementation:

- Current fetch path is a normalized health snapshot endpoint, not a direct provider call from the skill.
- Provider details should stay upstream; the local sink contract should not depend on a specific health vendor.
- The script writes to `reference/health/` under the current repo root by default.
- Use `--output-root` only when the sink should live somewhere else.
- The default person selector is the current repo root name, overridden by `--person` only when needed.
- The current snapshot endpoint supports `adi` and `angie`; keep separate sink roots or separate repos per person.
