#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"
FAIL_COUNT=0

workspace=$(mktemp -d)
trap 'rm -rf "$workspace"' EXIT
mkdir -p "$workspace/state"
cat >"$workspace/state/shelf.json" <<'JSON'
{
  "schemaVersion": 2,
  "revision": 1,
  "timezone": "Europe/Berlin",
  "updatedAt": "2026-06-06T17:00:00.000Z",
  "items": [
    {
      "id": "buy-oats",
      "type": "buy",
      "title": "Buy oats",
      "state": "active",
      "showOn": "2026-06-07",
      "deferCount": 0,
      "createdAt": "2026-06-06T17:00:00.000Z",
      "updatedAt": "2026-06-06T17:00:00.000Z"
    },
    {
      "id": "daily-water",
      "type": "habit",
      "title": "Water bottle",
      "state": "active",
      "schedule": { "cadence": "daily", "startOn": "2026-06-01" },
      "completions": [],
      "createdAt": "2026-06-06T17:00:00.000Z",
      "updatedAt": "2026-06-06T17:00:00.000Z"
    }
  ]
}
JSON

section "valid v2 shelf"
"$SKILL_DIR/scripts/validate" --workspace-root "$workspace" state/shelf.json --no-input >/dev/null
assert_exit "validate exit 0" 0 "$?"

section "reject v1 isNow"
python3 - <<PY
import json, pathlib
p=pathlib.Path('$workspace/state/shelf.json')
data=json.loads(p.read_text())
data['items'][0]['isNow']=True
p.write_text(json.dumps(data))
PY
if "$SKILL_DIR/scripts/validate" --workspace-root "$workspace" state/shelf.json --no-input >/tmp/validate-out 2>/tmp/validate-err; then
  assert_eq "validate rejected isNow" "1" "0"
else
  assert_contains "reject mentions v1" "v1 field" "$(cat /tmp/validate-err)"
fi

finish_test "shelf/validate.sh"
