#!/usr/bin/env bash
# Tests for `dobby memory boot`.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

section "memory boot — JSON default"
run_dobby memory boot
assert_exit "exit 0 on success" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.boot default" "$CAPTURED_STDOUT"
assert_jq_eq "command=memory.boot" '.command' "memory.boot" "$CAPTURED_STDOUT"
assert_jq_truthy "data.profile is a non-empty string" \
    '(.data.profile | type) == "string" and (.data.profile | length > 0)' "$CAPTURED_STDOUT"
assert_jq_truthy "data.now is a non-empty string" \
    '(.data.now | type) == "string" and (.data.now | length > 0)' "$CAPTURED_STDOUT"
assert_jq_truthy "data.areas is an array" \
    '(.data.areas | type) == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "data.counts.area_files is >= 1" \
    '.data.counts.area_files >= 1' "$CAPTURED_STDOUT"
assert_eq "stderr clean on success" "" "$CAPTURED_STDERR"

section "memory boot --plain returns markdown"
run_dobby memory boot --plain
assert_exit "exit 0 on success" 0 "$CAPTURED_EXIT"
assert_contains "contains profile marker comment" \
    "<!-- dobby memory boot: profile" "$CAPTURED_STDOUT"
assert_contains "contains now marker comment" \
    "<!-- dobby memory boot: now" "$CAPTURED_STDOUT"
assert_contains "contains areas marker comment" \
    "<!-- dobby memory boot: areas" "$CAPTURED_STDOUT"
assert_contains "references an area file path" \
    "memory/areas/" "$CAPTURED_STDOUT"
assert_not_contains "stdout has no JSON envelope" \
    '"schema_version"' "$CAPTURED_STDOUT"
assert_eq "stderr clean on success" "" "$CAPTURED_STDERR"

section "memory boot --json"
run_dobby memory boot --json
assert_exit "exit 0 on success" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.boot" "$CAPTURED_STDOUT"
assert_jq_eq "command=memory.boot" '.command' "memory.boot" "$CAPTURED_STDOUT"
assert_jq_truthy "data.profile is a non-empty string" \
    '(.data.profile | type) == "string" and (.data.profile | length > 0)' "$CAPTURED_STDOUT"
assert_jq_truthy "data.now is a non-empty string" \
    '(.data.now | type) == "string" and (.data.now | length > 0)' "$CAPTURED_STDOUT"
assert_jq_truthy "data.areas is an array" \
    '(.data.areas | type) == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "data.counts.area_files is >= 1" \
    '.data.counts.area_files >= 1' "$CAPTURED_STDOUT"

section "memory boot is cwd-independent"
# Run from /tmp with DOBBY_WORKSPACE set to make sure script location is decoupled from workspace location.
pushd /tmp > /dev/null
run_dobby memory boot --json
assert_exit "exit 0 from /tmp" 0 "$CAPTURED_EXIT"
assert_jq_eq "command stays memory.boot" '.command' "memory.boot" "$CAPTURED_STDOUT"
popd > /dev/null

finish_test "memory/boot.sh"
