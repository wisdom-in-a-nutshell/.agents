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
cat > "$TMP_WS/state/shelf.json" <<'JSON'
{
  "schemaVersion": 2,
  "revision": 0,
  "timezone": "Europe/Berlin",
  "updatedAt": "1970-01-01T00:00:00.000Z",
  "items": []
}
JSON
export DOBBY_WORKSPACE="$TMP_WS"
UPCOMING_DATE="$(python3 - <<'PY'
from datetime import date, timedelta
print((date.today() + timedelta(days=30)).isoformat())
PY
)"
DEFER_DATE="$(python3 - <<'PY'
from datetime import date, timedelta
print((date.today() + timedelta(days=31)).isoformat())
PY
)"
TODAY="$(TZ=Europe/Berlin date +%F)"

section "list empty shelf"
run_dobby shelf list
assert_exit "list exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.list" "$CAPTURED_STDOUT"
assert_jq_eq "active count 0" '.data.counts.active' "0" "$CAPTURED_STDOUT"

section "add item"
run_dobby shelf add --title "Test Shelf Client" --type do --show-on "$UPCOMING_DATE" --note "from test" --id test-shelf-client
assert_exit "add exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.add" "$CAPTURED_STDOUT"
assert_jq_eq "id set" '.data.item.id' "test-shelf-client" "$CAPTURED_STDOUT"
assert_jq_eq "type set" '.data.item.type' "do" "$CAPTURED_STDOUT"
assert_jq_eq "revision incremented" '.data.revision' "1" "$CAPTURED_STDOUT"

section "edit note"
run_dobby shelf note test-shelf-client --append "second note"
assert_exit "note append exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.note" "$CAPTURED_STDOUT"
assert_jq_eq "note appended" '.data.item.note' $'from test\n\nsecond note' "$CAPTURED_STDOUT"

section "list upcoming"
run_dobby shelf list --view upcoming
assert_exit "upcoming exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.list upcoming" "$CAPTURED_STDOUT"
assert_jq_eq "one item" '.data.cards | length' "1" "$CAPTURED_STDOUT"
assert_jq_eq "item title" '.data.cards[0].title' "Test Shelf Client" "$CAPTURED_STDOUT"

section "defer item"
run_dobby shelf defer test-shelf-client --show-on "$DEFER_DATE"
assert_exit "defer exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.defer" "$CAPTURED_STDOUT"
assert_jq_eq "showOn updated" '.data.item.showOn' "$DEFER_DATE" "$CAPTURED_STDOUT"
assert_jq_eq "deferCount incremented" '.data.item.deferCount' "1" "$CAPTURED_STDOUT"

section "complete item"
run_dobby shelf complete test-shelf-client
assert_exit "complete exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.complete" "$CAPTURED_STDOUT"
assert_jq_eq "state completed" '.data.item.state' "completed" "$CAPTURED_STDOUT"
assert_jq_truthy "completedAt set" '.data.item.completedAt' "$CAPTURED_STDOUT"

section "add habit"
run_dobby shelf habit add --title "No coffee" --cadence daily --start-on "$TODAY" --id no-coffee
assert_exit "habit add exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.habit.add" "$CAPTURED_STDOUT"
assert_jq_eq "habit type" '.data.item.type' "habit" "$CAPTURED_STDOUT"
run_dobby shelf snapshot --mode full
habit_card=$(jq -r '.data.views.today[] | select(.itemId=="no-coffee") | .cardId' <<<"$CAPTURED_STDOUT")
run_dobby shelf complete "$habit_card"
assert_exit "habit complete exit 0" 0 "$CAPTURED_EXIT"
assert_jq_eq "habit still active" '.data.item.state' "active" "$CAPTURED_STDOUT"
assert_jq_eq "habit completion length" '.data.item.completions | length' "1" "$CAPTURED_STDOUT"

section "drop missing item returns not found"
run_dobby shelf drop nope --reason "missing"
assert_exit "drop missing exit 1" 1 "$CAPTURED_EXIT"
assert_envelope_error "shelf.drop missing" "E_NOT_FOUND" "$CAPTURED_STDOUT"

section "file revision persisted"
rev=$(jq -r '.revision' "$TMP_WS/state/shelf.json")
assert_eq "revision after mutations" "6" "$rev"
state=$(jq -r '.items[] | select(.id=="test-shelf-client") | .state' "$TMP_WS/state/shelf.json")
assert_eq "file state completed" "completed" "$state"

finish_test "shelf/crud.sh"
