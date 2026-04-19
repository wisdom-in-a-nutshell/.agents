#!/usr/bin/env bash
# Live round-trip tests for `dobby tasks` via AppleScript/JXA.
#
# Requires Things 3 to be installed and running on this Mac.
# Self-skips if Things 3 isn't available.
#
# All scratch items use a timestamped prefix so they never collide with real
# tasks. A trap cleans them up even on failure.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

# Preflight
run_dobby tasks doctor --json
if [[ "$(printf '%s' "$CAPTURED_STDOUT" | jq -r '.data.ok // false')" != "true" ]]; then
    printf "\033[33mSKIP tasks/live.sh — Things 3 doctor reports unhealthy\033[0m\n"
    exit 0
fi

PREFIX="DOBBY-TEST-$(date +%s)"
CREATED_NAMES=()

cleanup() {
    for name in "${CREATED_NAMES[@]}"; do
        "$DOBBY" tasks delete "$name" --yes > /dev/null 2>&1 || true
    done
}
trap cleanup EXIT

section "add a task (plain default)"
run_dobby tasks add "$PREFIX alpha" --when today
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "says created" "created:" "$CAPTURED_STDOUT"
CREATED_NAMES+=("$PREFIX alpha")
sleep 1  # let URL scheme settle

section "add a second task (--json)"
run_dobby tasks add "$PREFIX beta" --when today --notes "test notes" --tags "urgent" --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.add beta" "$CAPTURED_STDOUT"
assert_jq_eq "title echoed" '.data.title' "$PREFIX beta" "$CAPTURED_STDOUT"
CREATED_NAMES+=("$PREFIX beta")
sleep 1

section "today contains the tasks"
run_dobby tasks today
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "alpha in today" "$PREFIX alpha" "$CAPTURED_STDOUT"
assert_contains "beta in today" "$PREFIX beta" "$CAPTURED_STDOUT"

section "today --json returns structured list"
run_dobby tasks today --json
assert_envelope_ok "tasks.today" "$CAPTURED_STDOUT"
assert_jq_truthy "count >= 2" '.data.count >= 2' "$CAPTURED_STDOUT"

section "search finds both"
run_dobby tasks search "$PREFIX" --json
assert_envelope_ok "tasks.search" "$CAPTURED_STDOUT"
assert_jq_truthy "count >= 2" '.data.count >= 2' "$CAPTURED_STDOUT"

section "mark alpha done"
run_dobby tasks done "$PREFIX alpha"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "says done" "done:" "$CAPTURED_STDOUT"

section "alpha no longer in today"
# Ride out potential delay
found=0
for attempt in 1 2 3; do
    run_dobby tasks today
    if [[ "$CAPTURED_STDOUT" != *"$PREFIX alpha"* ]]; then
        found=1
        break
    fi
    sleep 1
done
if (( found )); then
    _pass "alpha removed from today"
else
    _fail "alpha removed from today" "still visible"
fi

section "search --include-completed finds alpha"
run_dobby tasks search "$PREFIX alpha" --include-completed --json
assert_jq_truthy "found completed alpha" '.data.count >= 1' "$CAPTURED_STDOUT"

section "delete beta"
run_dobby tasks delete "$PREFIX beta" --yes
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "says deleted" "deleted:" "$CAPTURED_STDOUT"
# Remove from cleanup list since it's already deleted
CREATED_NAMES=("$PREFIX alpha")

section "delete without --yes is rejected"
run_dobby tasks delete "anything"
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.delete no --yes" "E_VALIDATION" "$CAPTURED_STDOUT"

section "cleanup alpha (best-effort — completed tasks may be auto-logged)"
# Completed tasks move to Logbook after `log completed now`. They may become
# unfindable by name. This is best-effort cleanup.
run_dobby tasks delete "$PREFIX alpha" --yes
if [[ "$CAPTURED_EXIT" -eq 0 ]]; then
    _pass "alpha cleanup succeeded"
else
    _pass "alpha cleanup skipped (task already logged/trashed — expected for completed items)"
fi
CREATED_NAMES=()

section "post-cleanup: no open test tasks remain"
run_dobby tasks search "$PREFIX"
assert_eq "no open tasks remain" "(no matches)" "$CAPTURED_STDOUT"

finish_test "tasks/live.sh"
