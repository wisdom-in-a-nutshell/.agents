#!/usr/bin/env bash
# Tests for `dobby memory write`.
#
# Uses a temporary scratch file under memory/areas/builder/ so it exercises
# the real routing logic without touching now, becoming, or any durable area
# file. Cleans up on EXIT, even on test failure.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0
SCRATCH="$REPO_ROOT/memory/areas/builder/dobby-test-scratch.md"

cleanup() {
    rm -f "$SCRATCH"
}
trap cleanup EXIT

# Start fresh scratch target
echo "# Dobby test scratch (safe to delete)" > "$SCRATCH"

section "memory write — empty stdin rejected"
run_dobby_stdin "" memory write --section area.builder.dobby-test-scratch
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "memory.write empty" "E_VALIDATION" "$CAPTURED_STDOUT"

section "memory write — nonexistent target rejected"
run_dobby_stdin "hello" memory write --section area.nope.missing
assert_exit "exit 1" 1 "$CAPTURED_EXIT"
assert_envelope_error "memory.write not-found" "E_NOT_FOUND" "$CAPTURED_STDOUT"

section "memory write — directory target rejected"
# area.builder resolves to the directory, not a file
run_dobby_stdin "hello" memory write --section area.builder
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "memory.write directory" "E_VALIDATION" "$CAPTURED_STDOUT"

section "memory write — JSON default success"
BEFORE=$(wc -c < "$SCRATCH")
run_dobby_stdin "First appended line" memory write --section area.builder.dobby-test-scratch --message "first contract test"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.write default" "$CAPTURED_STDOUT"
assert_jq_eq "command=memory.write" '.command' "memory.write" "$CAPTURED_STDOUT"
assert_jq_eq "section is echoed" '.data.section' "area.builder.dobby-test-scratch" "$CAPTURED_STDOUT"
assert_jq_truthy "bytes_appended > 0" '.data.bytes_appended > 0' "$CAPTURED_STDOUT"
AFTER=$(wc -c < "$SCRATCH")
if [[ $AFTER -gt $BEFORE ]]; then
    _pass "scratch file grew"
else
    _fail "scratch file grew" "size unchanged ($BEFORE -> $AFTER)"
fi
assert_contains "file contains new content" "First appended line" "$(cat "$SCRATCH")"
assert_contains "file contains write-marker header" "dobby write" "$(cat "$SCRATCH")"
assert_contains "file contains message" "first contract test" "$(cat "$SCRATCH")"

section "memory write --plain returns one-liner"
run_dobby_stdin "Second appended line" memory write --section area.builder.dobby-test-scratch --plain --message "second contract test"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "plain stdout mentions bytes appended" "wrote " "$CAPTURED_STDOUT"
assert_contains "plain stdout references path" "memory/areas/builder/dobby-test-scratch.md" "$CAPTURED_STDOUT"
assert_not_contains "plain stdout has no envelope" '"schema_version"' "$CAPTURED_STDOUT"

section "memory write --json returns envelope"
run_dobby_stdin "Third appended line" memory write --section area.builder.dobby-test-scratch --json --message "third contract test"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.write --json" "$CAPTURED_STDOUT"
assert_jq_eq "command=memory.write" '.command' "memory.write" "$CAPTURED_STDOUT"
assert_jq_eq "section is echoed" '.data.section' "area.builder.dobby-test-scratch" "$CAPTURED_STDOUT"
assert_jq_truthy "bytes_appended > 0" '.data.bytes_appended > 0' "$CAPTURED_STDOUT"

section "memory write — stderr stays clean on success"
run_dobby_stdin "Quiet run" memory write --section area.builder.dobby-test-scratch
assert_eq "stderr empty" "" "$CAPTURED_STDERR"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"

finish_test "memory/write.sh"
