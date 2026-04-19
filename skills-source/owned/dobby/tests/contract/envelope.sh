#!/usr/bin/env bash
# Cross-command contract tests.
#
# Ensures every command that returns a JSON envelope produces the full stable
# shape (schema_version, command, status, data/error, meta with
# request_id/duration_ms/timestamp_utc) and that stdout vs stderr stays clean.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

section "schema_version stability across commands"
for cmd in "memory boot --json" "memory read --section profile --json" "memory diff --json" "tasks doctor --json" "calendar doctor"; do
    run_dobby $cmd
    assert_jq_eq "$cmd: schema_version=1.0" '.schema_version' "1.0" "$CAPTURED_STDOUT"
done

section "meta fields present on success"
run_dobby memory boot --json
assert_jq_truthy "request_id is 32 hex chars" \
    '(.meta.request_id | test("^[a-f0-9]{32}$"))' "$CAPTURED_STDOUT"
assert_jq_truthy "duration_ms is a number >= 0" \
    '(.meta.duration_ms | type) == "number" and .meta.duration_ms >= 0' "$CAPTURED_STDOUT"
assert_jq_truthy "timestamp_utc has Z suffix" \
    '(.meta.timestamp_utc | test("Z$"))' "$CAPTURED_STDOUT"

section "meta fields present on error"
run_dobby memory read --section bogus
assert_jq_truthy "error request_id is 32 hex chars" \
    '(.meta.request_id | test("^[a-f0-9]{32}$"))' "$CAPTURED_STDOUT"
assert_jq_truthy "error meta has duration_ms" \
    '(.meta | has("duration_ms"))' "$CAPTURED_STDOUT"
assert_jq_truthy "error meta has timestamp_utc" \
    '(.meta | has("timestamp_utc"))' "$CAPTURED_STDOUT"

section "error envelope has all required fields"
run_dobby memory read --section bogus
assert_jq_truthy "error.code is string" '(.error.code | type) == "string"' "$CAPTURED_STDOUT"
assert_jq_truthy "error.message is string" '(.error.message | type) == "string"' "$CAPTURED_STDOUT"
assert_jq_truthy "error.retryable is bool" '(.error.retryable | type) == "boolean"' "$CAPTURED_STDOUT"
assert_jq_truthy "error.hint is string" '(.error.hint | type) == "string"' "$CAPTURED_STDOUT"

section "exit code mapping (stable)"
# E_VALIDATION -> 2
run_dobby memory read --section bogus
assert_exit "E_VALIDATION -> exit 2" 2 "$CAPTURED_EXIT"
# E_NOT_FOUND -> 1
run_dobby memory read --section area.nope
assert_exit "E_NOT_FOUND -> exit 1" 1 "$CAPTURED_EXIT"
# E_VALIDATION from tasks.add empty title
run_dobby tasks add ""
assert_exit "tasks.add empty -> exit 2" 2 "$CAPTURED_EXIT"

section "stdout is clean JSON for --json commands (no prefix/suffix)"
run_dobby memory boot --json
# First non-whitespace char of stdout should be '{'
first_char=$(printf '%s' "$CAPTURED_STDOUT" | head -c 1)
assert_eq "stdout starts with {" "{" "$first_char"
# stdout parses as a single JSON object
if printf '%s' "$CAPTURED_STDOUT" | jq empty > /dev/null 2>&1; then
    _pass "stdout parses as single JSON"
else
    _fail "stdout parses as single JSON" "jq could not parse stdout"
fi

section "stderr stays clean on success"
run_dobby memory boot
assert_eq "memory boot stderr empty" "" "$CAPTURED_STDERR"
run_dobby memory boot --json
assert_eq "memory boot --json stderr empty" "" "$CAPTURED_STDERR"
run_dobby memory read --section profile
assert_eq "memory read profile stderr empty" "" "$CAPTURED_STDERR"

finish_test "contract/envelope.sh"
