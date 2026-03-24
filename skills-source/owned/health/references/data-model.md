# Health Sink Data Model

Canonical sink root:

- `reference/health/`

Primary split:

- `profile/` for stable structured health facts
- `metrics/` for recurring structured JSON data
- `records/` for documents and irregular artifacts

Stable profile pattern:

- `profile/latest.json` is the canonical home for structured facts that are
  important for lookup or calculations but are not naturally time-series data.
- Example fits:
  - height
  - other mostly-static body facts when they become useful later
- Keep durable support-relevant interpretation in memory, but keep the factual
  structured value itself in `profile/`.

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
2. For stable body/profile facts, read `profile/latest.json`.
3. Read `latest.json` first when inspecting raw files manually.
4. Only inspect `by-date/` when the user wants trend/history or when the query script does not cover the question yet.
5. Treat `weight/` and `body-composition/` as separate datasets.
6. Treat `metrics/sleep/stages/` as the real sleep source today.
7. Do not rely on `metrics/sleep/summary/` unless it actually contains rows; the current snapshot for this account/source may be empty.

Current upstream implementation:

- Current fetch path is a normalized health snapshot endpoint, not a direct provider call from the skill.
- Provider details should stay upstream; the local sink contract should not depend on a specific health vendor.
- The script writes to `reference/health/` under the current repo root by default.
- Use `--output-root` only when the sink should live somewhere else.
- The default person selector is the current repo root name, overridden by `--person` only when needed.
- The current snapshot endpoint supports `adi` and `angie`; keep separate sink roots or separate repos per person.
