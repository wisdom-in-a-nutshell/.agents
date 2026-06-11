#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"
FAIL_COUNT=0

TMP_WS=$(mktemp -d)
trap 'rm -rf "$TMP_WS"' EXIT
mkdir -p "$TMP_WS/state" "$TMP_WS/memory" "$TMP_WS/journal" "$TMP_WS/dobby"
cat > "$TMP_WS/dobby/constitution.md" <<'MD'
---
schemaVersion: 2
kind: dobby-constitution
updatedAt: 2026-05-31T00:00:00+02:00
sensitivity: personal
---

# Test constitution
MD
TODAY="$(TZ=Europe/Berlin date +%F)"
TOMORROW="$(python3 - <<'PY'
from datetime import date, timedelta
print((date.today() + timedelta(days=1)).isoformat())
PY
)"
cat > "$TMP_WS/state/shelf.json" <<JSON
{
  "schemaVersion": 2,
  "revision": 7,
  "timezone": "Europe/Berlin",
  "updatedAt": "2026-06-04T08:00:00.000Z",
  "items": [
    {
      "id": "today-item",
      "type": "do",
      "title": "Current task",
      "state": "active",
      "showOn": "$TODAY",
      "createdAt": "2026-06-01T08:00:00.000Z",
      "updatedAt": "2026-06-01T08:00:00.000Z",
      "deferCount": 0,
      "note": "Long note should only appear as a compact preview."
    },
    {
      "id": "later-item",
      "type": "do",
      "title": "Unscheduled later item",
      "state": "active",
      "createdAt": "2026-06-02T08:00:00.000Z",
      "updatedAt": "2026-06-02T08:00:00.000Z",
      "deferCount": 0
    },
    {
      "id": "daily-habit",
      "type": "habit",
      "title": "Daily habit",
      "state": "active",
      "schedule": { "cadence": "daily", "startOn": "$TODAY" },
      "completions": [],
      "createdAt": "2026-06-02T08:00:00.000Z",
      "updatedAt": "2026-06-02T08:00:00.000Z"
    }
  ]
}
JSON
export DOBBY_WORKSPACE="$TMP_WS"

section "boot snapshot uses Today/Upcoming/Later"
run_dobby shelf snapshot --mode boot
assert_exit "boot snapshot exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.snapshot boot" "$CAPTURED_STDOUT"
assert_jq_eq "schema v2" '.data.schemaVersion' "2" "$CAPTURED_STDOUT"
assert_jq_eq "today visible" '.data.views.today | length' "2" "$CAPTURED_STDOUT"
assert_jq_eq "later hidden by boot" '.data.views.later | length' "0" "$CAPTURED_STDOUT"
assert_jq_eq "later hidden count" '.data.hiddenCounts.later' "1" "$CAPTURED_STDOUT"
assert_jq_eq "no now view" '.data.views | has("now")' "false" "$CAPTURED_STDOUT"

section "habit complete hides today's occurrence"
habit_card=$(jq -r '.data.views.today[] | select(.type=="habit") | .cardId' <<<"$CAPTURED_STDOUT")
run_dobby shelf complete "$habit_card"
assert_exit "complete habit exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.complete habit" "$CAPTURED_STDOUT"
assert_jq_eq "completion recorded" '.data.item.completions | length' "1" "$CAPTURED_STDOUT"
run_dobby shelf snapshot --mode full
assert_exit "snapshot after habit complete" 0 "$CAPTURED_EXIT"
assert_jq_eq "habit hidden today" '[.data.views.today[] | select(.type=="habit")] | length' "0" "$CAPTURED_STDOUT"

finish_test "shelf/snapshot.sh"
