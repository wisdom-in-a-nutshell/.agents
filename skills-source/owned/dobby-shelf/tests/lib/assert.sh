#!/usr/bin/env bash
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$(cd "$TESTS_DIR/.." && pwd)"
DOBBY="$TESTS_DIR/support/dobby-shim"
DOBBY_SHELF="$SKILL_DIR/scripts/dobby-shelf"
export FAIL_COUNT=${FAIL_COUNT:-0}

_pass() { printf "  \033[32m✓\033[0m %s\n" "$1"; }
_fail() { printf "  \033[31m✗\033[0m %s: %s\n" "$1" "$2"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
section() { printf "\n\033[1m%s\033[0m\n" "$1"; }

assert_eq() { local name="$1" expected="$2" actual="$3"; if [[ "$expected" == "$actual" ]]; then _pass "$name"; else _fail "$name" "expected $(printf '%q' "$expected"), got $(printf '%q' "$actual")"; fi; }
assert_contains() { local name="$1" needle="$2" haystack="$3"; if [[ "$haystack" == *"$needle"* ]]; then _pass "$name"; else _fail "$name" "did not find $(printf '%q' "$needle")"; fi; }
assert_not_contains() { local name="$1" needle="$2" haystack="$3"; if [[ "$haystack" != *"$needle"* ]]; then _pass "$name"; else _fail "$name" "unexpectedly found $(printf '%q' "$needle")"; fi; }
assert_exit() { local name="$1" expected="$2" actual="$3"; if [[ "$expected" -eq "$actual" ]]; then _pass "$name"; else _fail "$name" "expected exit $expected, got $actual"; fi; }
assert_jq_eq() { local name="$1" expr="$2" expected="$3" json="$4"; local actual; actual=$(printf '%s' "$json" | jq -r "$expr" 2>/dev/null || echo "<jq-error>"); assert_eq "$name" "$expected" "$actual"; }
assert_jq_truthy() { local name="$1" expr="$2" json="$3"; local actual; actual=$(printf '%s' "$json" | jq "$expr" 2>/dev/null || echo "false"); if [[ "$actual" == "true" ]] || [[ "$actual" != "null" && -n "$actual" && "$actual" != "false" ]]; then _pass "$name"; else _fail "$name" "expected truthy for $expr, got $actual"; fi; }

assert_envelope_shape() {
    local name_prefix="$1" json="$2"
    assert_jq_eq "$name_prefix: schema_version=1.0" '.schema_version' "1.0" "$json"
    assert_jq_truthy "$name_prefix: has command field" '.command' "$json"
    assert_jq_truthy "$name_prefix: has status field" '.status' "$json"
    assert_jq_truthy "$name_prefix: has meta.request_id" '.meta.request_id' "$json"
    assert_jq_truthy "$name_prefix: has meta.duration_ms" '.meta | has("duration_ms")' "$json"
    assert_jq_truthy "$name_prefix: has meta.timestamp_utc" '.meta.timestamp_utc' "$json"
}
assert_envelope_ok() {
    local name_prefix="$1" json="$2"
    assert_envelope_shape "$name_prefix" "$json"
    assert_jq_eq "$name_prefix: status=ok" '.status' "ok" "$json"
    assert_jq_eq "$name_prefix: error is null" '.error' "null" "$json"
    assert_jq_truthy "$name_prefix: data is not null" '.data != null' "$json"
}
assert_envelope_error() {
    local name_prefix="$1" expected_code="$2" json="$3"
    assert_envelope_shape "$name_prefix" "$json"
    assert_jq_eq "$name_prefix: status=error" '.status' "error" "$json"
    assert_jq_eq "$name_prefix: data is null" '.data' "null" "$json"
    assert_jq_eq "$name_prefix: error.code=$expected_code" '.error.code' "$expected_code" "$json"
    assert_jq_truthy "$name_prefix: error.message non-empty" '.error.message' "$json"
}

run_dobby() {
    local stdout_file stderr_file
    stdout_file=$(mktemp); stderr_file=$(mktemp)
    set +e
    "$DOBBY" "$@" > "$stdout_file" 2> "$stderr_file"
    CAPTURED_EXIT=$?
    set -e
    CAPTURED_STDOUT=$(cat "$stdout_file")
    CAPTURED_STDERR=$(cat "$stderr_file")
    rm -f "$stdout_file" "$stderr_file"
}

finish_test() {
    local script_name="${1:-test}"
    if [[ $FAIL_COUNT -eq 0 ]]; then printf "\n\033[32m%s: PASS\033[0m\n" "$script_name"; else printf "\n\033[31m%s: FAIL (%d failures)\033[0m\n" "$script_name" "$FAIL_COUNT"; fi
    if [[ $FAIL_COUNT -gt 255 ]]; then return 255; fi
    return "$FAIL_COUNT"
}
