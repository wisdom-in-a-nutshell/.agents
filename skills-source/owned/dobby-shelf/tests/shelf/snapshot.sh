#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"
FAIL_COUNT=0

TMP_WS=$(mktemp -d)
trap 'rm -rf "$TMP_WS"' EXIT
mkdir -p "$TMP_WS/state" "$TMP_WS/memory" "$TMP_WS/journal" "$TMP_WS/dobby"
printf '{"schemaVersion":1,"kind":"dobby-constitution","updatedAt":"2026-05-31T00:00:00+02:00","groups":{}}\n' > "$TMP_WS/dobby/constitution.json"
cat > "$TMP_WS/state/shelf.json" <<'JSON'
{
  "schemaVersion": 1,
  "revision": 7,
  "updatedAt": "2026-06-04T08:00:00.000Z",
  "items": [
    {
      "id": "focus-item",
      "title": "Current focus",
      "kind": "do",
      "status": "open",
      "isNow": true,
      "createdAt": "2026-06-01T08:00:00.000Z",
      "updatedAt": "2026-06-01T08:00:00.000Z",
      "deferCount": 0,
      "note": "Long note should not appear in compact snapshot."
    },
    {
      "id": "later-item",
      "title": "Unscheduled later item",
      "kind": "do",
      "status": "open",
      "createdAt": "2026-06-02T08:00:00.000Z",
      "updatedAt": "2026-06-02T08:00:00.000Z",
      "deferCount": 0
    }
  ]
}
JSON
export DOBBY_WORKSPACE="$TMP_WS"

section "boot snapshot hides later item details"
run_dobby shelf snapshot --mode boot
assert_exit "boot snapshot exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.snapshot boot" "$CAPTURED_STDOUT"
assert_jq_eq "boot now visible" '.data.sections.now | length' "1" "$CAPTURED_STDOUT"
assert_jq_eq "boot later hidden" '.data.sections.later | length' "0" "$CAPTURED_STDOUT"
assert_jq_eq "boot later hidden count" '.data.hidden_counts.later' "1" "$CAPTURED_STDOUT"
assert_jq_eq "boot compact omits note" '.data.sections.now[0] | has("note")' "false" "$CAPTURED_STDOUT"

section "full snapshot includes later item details"
run_dobby shelf snapshot --mode full
assert_exit "full snapshot exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.snapshot full" "$CAPTURED_STDOUT"
assert_jq_eq "full later visible" '.data.sections.later | length' "1" "$CAPTURED_STDOUT"
assert_jq_eq "full later id" '.data.sections.later[0].id' "later-item" "$CAPTURED_STDOUT"
assert_jq_eq "full later hidden count" '.data.hidden_counts.later' "0" "$CAPTURED_STDOUT"

finish_test "shelf/snapshot.sh"
