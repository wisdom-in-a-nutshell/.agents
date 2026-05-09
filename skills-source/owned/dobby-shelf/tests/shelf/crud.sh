#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"
FAIL_COUNT=0

TMP_WS=$(mktemp -d)
trap 'rm -rf "$TMP_WS"' EXIT
mkdir -p "$TMP_WS/state" "$TMP_WS/memory" "$TMP_WS/journal"
printf '# Test soul\n' > "$TMP_WS/soul.md"
cat > "$TMP_WS/state/shelf.json" <<'JSON'
{
  "schemaVersion": 1,
  "revision": 0,
  "updatedAt": "1970-01-01T00:00:00.000Z",
  "items": []
}
JSON
export DOBBY_WORKSPACE="$TMP_WS"

section "list empty shelf"
run_dobby shelf list
assert_exit "list exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.list" "$CAPTURED_STDOUT"
assert_jq_eq "command=shelf.list" '.command' "shelf.list" "$CAPTURED_STDOUT"
assert_jq_eq "open count 0" '.data.counts.open' "0" "$CAPTURED_STDOUT"

section "add item"
run_dobby shelf add --title "Test Shelf Client" --kind do --show-at 2026-05-10 --note "from test" --id test-shelf-client
assert_exit "add exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.add" "$CAPTURED_STDOUT"
assert_jq_eq "id set" '.data.item.id' "test-shelf-client" "$CAPTURED_STDOUT"
assert_jq_eq "revision incremented" '.data.revision' "1" "$CAPTURED_STDOUT"

section "list upcoming"
run_dobby shelf list --view upcoming
assert_exit "upcoming exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.list upcoming" "$CAPTURED_STDOUT"
assert_jq_eq "one item" '.data.items | length' "1" "$CAPTURED_STDOUT"
assert_jq_eq "item title" '.data.items[0].title' "Test Shelf Client" "$CAPTURED_STDOUT"

section "focus and plain list"
run_dobby shelf focus test-shelf-client --on
assert_exit "focus exit 0" 0 "$CAPTURED_EXIT"
assert_jq_eq "isNow true" '.data.item.isNow' "true" "$CAPTURED_STDOUT"
run_dobby shelf list --view now --plain
assert_exit "plain now exit 0" 0 "$CAPTURED_EXIT"
assert_contains "plain includes id" "test-shelf-client" "$CAPTURED_STDOUT"
assert_not_contains "plain no json" '"schema_version"' "$CAPTURED_STDOUT"

section "defer item"
run_dobby shelf defer test-shelf-client --show-at 2026-05-12
assert_exit "defer exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.defer" "$CAPTURED_STDOUT"
assert_jq_eq "showAt updated" '.data.item.showAt' "2026-05-12" "$CAPTURED_STDOUT"
assert_jq_eq "deferCount incremented" '.data.item.deferCount' "1" "$CAPTURED_STDOUT"

section "done item"
run_dobby shelf done test-shelf-client
assert_exit "done exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "shelf.done" "$CAPTURED_STDOUT"
assert_jq_eq "status done" '.data.item.status' "done" "$CAPTURED_STDOUT"
assert_jq_truthy "completedAt set" '.data.item.completedAt' "$CAPTURED_STDOUT"

section "drop missing item returns not found"
run_dobby shelf drop nope --reason "missing"
assert_exit "drop missing exit 1" 1 "$CAPTURED_EXIT"
assert_envelope_error "shelf.drop missing" "E_NOT_FOUND" "$CAPTURED_STDOUT"

section "file revision persisted"
rev=$(jq -r '.revision' "$TMP_WS/state/shelf.json")
assert_eq "revision after mutations" "4" "$rev"
status=$(jq -r '.items[0].status' "$TMP_WS/state/shelf.json")
assert_eq "file status done" "done" "$status"

finish_test "shelf/crud.sh"
