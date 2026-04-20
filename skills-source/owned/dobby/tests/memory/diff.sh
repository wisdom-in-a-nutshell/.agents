#!/usr/bin/env bash
# Tests for `dobby memory diff`.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

section "memory diff --since (JSON default)"
run_dobby memory diff --since "30 days ago"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.diff default" "$CAPTURED_STDOUT"
assert_jq_eq "command=memory.diff" '.command' "memory.diff" "$CAPTURED_STDOUT"
assert_jq_eq "since is echoed" '.data.since' "30 days ago" "$CAPTURED_STDOUT"
assert_jq_truthy "timeout exposed" '.data.timeout_secs > 0' "$CAPTURED_STDOUT"

section "memory diff --plain"
run_dobby memory diff --since "30 days ago" --plain
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_not_contains "stdout has no JSON envelope" '"schema_version"' "$CAPTURED_STDOUT"

section "memory diff --json"
run_dobby memory diff --since "30 days ago" --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.diff" "$CAPTURED_STDOUT"
assert_jq_eq "command=memory.diff" '.command' "memory.diff" "$CAPTURED_STDOUT"
assert_jq_eq "since is echoed" '.data.since' "30 days ago" "$CAPTURED_STDOUT"
assert_jq_truthy "bytes >= 0" '.data.bytes >= 0' "$CAPTURED_STDOUT"
assert_jq_truthy "is_empty is a bool" '(.data.is_empty | type) == "boolean"' "$CAPTURED_STDOUT"

section "memory diff — very old --since should yield deterministic output"
run_dobby memory diff --since "1 year ago" --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_jq_truthy "diff is a string" '(.data.diff | type) == "string"' "$CAPTURED_STDOUT"

finish_test "memory/diff.sh"
