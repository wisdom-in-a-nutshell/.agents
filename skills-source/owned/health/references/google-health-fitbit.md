# Google Health / Fitbit integration notes

Last researched: 2026-06-11.

## Decision

Build new Fitbit-device work against the **Google Health API**, not the legacy Fitbit Web API.

Why:

- Google says the Fitbit Web API has been modernized into the Google Health API.
- The legacy Fitbit Web API is scheduled to turn down in **September 2026**.
- New OAuth is Google OAuth 2.0, not Fitbit Authorization.
- The Google Health API exposes Fitbit and Pixel watch data through one `health.googleapis.com/v4` REST surface.

Primary docs:

- <https://developers.google.com/health/about>
- <https://developers.google.com/health/migration/data-access>
- <https://developers.google.com/health/migration/api-specifications>
- <https://developers.google.com/health/reference/rest>
- <https://developers.google.com/health/data-types>
- <https://developers.google.com/health/scopes>
- <https://developers.google.com/health/endpoints>
- <https://developers.google.com/health/rate-limits>

## Current Dobby architecture choice

Keep the current health architecture intact:

- Canonical read surface: `memory/areas/health/metrics/**` in the repo-local health sink.
- Current production sync: `scripts/sync_health.py` fetches the normalized WIN/backend snapshot.
- New client: `scripts/google_health_client.py` is a **low-level probe/client** for OAuth and raw payload exploration.
- Later consolidation should happen by normalizing Google Health data into the existing sink shape, preferably upstream in the snapshot API rather than making Dobby reason from raw provider payloads.

So: code belongs in the health skill; personal/raw output belongs in the health area or `tmp/`; secrets stay outside the repo.

## OAuth and local secrets

Google Health apps use Google Cloud OAuth credentials and restricted health scopes.

For local operator tooling, use machine-local shared secret storage:

```text
~/.secrets/google-health/env
~/.secrets/google-health/token.json
```

Expected env file keys:

```bash
GOOGLE_HEALTH_CLIENT_ID="...apps.googleusercontent.com"
GOOGLE_HEALTH_CLIENT_SECRET="..."
GOOGLE_HEALTH_REDIRECT_URI="https://www.google.com"
```

Do not commit OAuth client secrets, refresh tokens, or access tokens.

Default read scopes used by the probe client:

```text
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.profile.readonly
https://www.googleapis.com/auth/googlehealth.settings.readonly
https://www.googleapis.com/auth/googlehealth.sleep.readonly
```

Add narrower or broader scopes only when needed.

## Probe client commands

Build a browser auth URL:

```bash
python3 .agents/skills/health/scripts/google_health_client.py auth-url
```

If Google does not return a refresh token, retry with forced consent:

```bash
python3 .agents/skills/health/scripts/google_health_client.py auth-url --force-consent
```

Exchange the redirected `code=` value and save tokens locally:

```bash
python3 .agents/skills/health/scripts/google_health_client.py exchange-code --code 'AUTH_CODE_FROM_REDIRECT'
```

Refresh saved tokens:

```bash
python3 .agents/skills/health/scripts/google_health_client.py refresh-token
```

Read account/device surfaces:

```bash
python3 .agents/skills/health/scripts/google_health_client.py identity
python3 .agents/skills/health/scripts/google_health_client.py profile
python3 .agents/skills/health/scripts/google_health_client.py settings
python3 .agents/skills/health/scripts/google_health_client.py devices --all-pages
```

Probe activity/sleep/body data:

```bash
python3 .agents/skills/health/scripts/google_health_client.py daily-rollup steps \
  --start 2026-06-01 --end 2026-06-08 --all-pages

python3 .agents/skills/health/scripts/google_health_client.py reconcile heart-rate \
  --start 2026-06-01 --end 2026-06-02 --all-pages

python3 .agents/skills/health/scripts/google_health_client.py list sleep \
  --start 2026-06-01 --end 2026-06-08 --all-pages

python3 .agents/skills/health/scripts/google_health_client.py list weight \
  --start 2026-06-01 --end 2026-06-08 --all-pages
```

For edge cases, use raw requests:

```bash
python3 .agents/skills/health/scripts/google_health_client.py request GET /v4/users/me/profile
```

## Useful API facts

- Base URL: `https://health.googleapis.com`.
- Profile example: `GET /v4/users/me/profile`.
- Paired devices: `GET /v4/users/me/pairedDevices`.
- Raw data points: `GET /v4/users/me/dataTypes/{dataType}/dataPoints`.
- Reconciled data points: `GET /v4/users/me/dataTypes/{dataType}/dataPoints:reconcile`.
- Daily rollups: `POST /v4/users/me/dataTypes/{dataType}/dataPoints:dailyRollUp`.
- Physical-time rollups: `POST /v4/users/me/dataTypes/{dataType}/dataPoints:rollUp`.
- Data type identifiers are kebab-case in URLs, e.g. `heart-rate`, `body-fat`, `daily-resting-heart-rate`.
- Filter fields often use snake_case or lowerCamelCase depending on record type; if the client cannot infer a filter, pass `--filter` explicitly.
- For daily rollups, Google documents a 14-day max range for `calories-in-heart-rate-zone`, `heart-rate`, `active-minutes`, and `total-calories`; other listed types currently allow up to 90 days.
- Per-user rate limit is documented as 300 requests/minute; the client retries one `429` once using `Retry-After` where possible.

## Later normalization plan

When the device is active and OAuth works:

1. Capture small raw samples for these data types:
   - `steps`, `distance`, `active-zone-minutes`, `total-calories`
   - `exercise`
   - `sleep`
   - `heart-rate`, `daily-resting-heart-rate`, `heart-rate-variability`
   - `weight`, `body-fat` if Fitbit scale/body measurements are present
   - `pairedDevices`, `profile`, `settings`
2. Compare them to the current sink shape under `memory/areas/health/metrics/**`.
3. Add a normalizer that writes provider-tagged records into the existing sink.
4. Prefer an upstream normalized snapshot endpoint when this becomes regular, so Dobby keeps consuming one clean local sink rather than multiple raw provider APIs.
