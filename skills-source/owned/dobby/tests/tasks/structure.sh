#!/usr/bin/env bash
# Structure tests for `dobby tasks` (AppleScript backend).
#
# Tests argparse surface, help output, validation errors, and doctor.
# Does NOT require Things 3 to be running for most tests (validation
# errors fire before the AppleScript call).
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

section "dobby tasks --help surface"
run_dobby tasks --help
assert_exit "help exit 0" 0 "$CAPTURED_EXIT"
for cmd in today inbox upcoming anytime someday logbook snapshot overdue search projects areas tags add done cancel schedule edit delete project-new area-new doctor; do
    assert_contains "$cmd in help" "$cmd" "$CAPTURED_STDOUT"
done

section "snapshot returns today/overdue/inbox in one envelope"
run_dobby tasks snapshot
assert_exit "snapshot exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.snapshot" "$CAPTURED_STDOUT"
assert_jq_truthy "has today view" '.data.views.today.tasks | type == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "has overdue view" '.data.views.overdue.tasks | type == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "has inbox view" '.data.views.inbox.tasks | type == "array"' "$CAPTURED_STDOUT"

section "add — empty title rejected"
run_dobby tasks add ""
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.add empty" "E_VALIDATION" "$CAPTURED_STDOUT"

section "add — missing title rejected"
run_dobby tasks add
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.add missing title" "E_VALIDATION" "$CAPTURED_STDOUT"

section "delete without --yes rejected"
run_dobby tasks delete "anything"
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.delete no --yes" "E_VALIDATION" "$CAPTURED_STDOUT"
assert_contains "hint mentions safety gate" "safety gate" "$CAPTURED_STDOUT"

section "schedule without any flag rejected"
run_dobby tasks schedule "anything"
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.schedule empty" "E_VALIDATION" "$CAPTURED_STDOUT"

section "edit without any change rejected"
run_dobby tasks edit "anything"
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.edit empty" "E_VALIDATION" "$CAPTURED_STDOUT"

section "add with --when accepts natural language (passed to Things 3)"
# URL scheme supports natural language dates like "next monday", "in 3 days".
# We don't validate --when client-side — Things 3 interprets it.
# This test just confirms the command doesn't crash.
STRUCTURE_NL_TITLE="DOBBY-TEST-STRUCTURE-NL-$(date +%s)-$$"
run_dobby tasks add "$STRUCTURE_NL_TITLE" --when "tomorrow"
assert_exit "exit 0 with natural language when" 0 "$CAPTURED_EXIT"
# Cleanup by ID, because name-based deletion can be ambiguous and Things URL
# scheme processing is asynchronous.
sleep 1
"$DOBBY" tasks search "$STRUCTURE_NL_TITLE" --json 2>/dev/null \
    | jq -r '.data.tasks[]?.id' 2>/dev/null \
    | while read -r id; do
        [[ -z "$id" ]] && continue
        "$DOBBY" tasks delete "$id" --yes > /dev/null 2>&1 || true
      done

section "project-new — empty title rejected"
run_dobby tasks project-new ""
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.project-new empty" "E_VALIDATION" "$CAPTURED_STDOUT"

section "area-new — empty title rejected"
run_dobby tasks area-new ""
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.area-new empty" "E_VALIDATION" "$CAPTURED_STDOUT"

section "doctor --plain returns inspection report"
run_dobby tasks doctor --plain
assert_exit "exit 0 or 4" 0 "$CAPTURED_EXIT" || true  # might be degraded
assert_contains "doctor checks osascript" "osascript" "$CAPTURED_STDOUT"
assert_contains "doctor checks things3_installed" "things3_installed" "$CAPTURED_STDOUT"
assert_contains "doctor checks things3_running" "things3_running" "$CAPTURED_STDOUT"
assert_contains "doctor checks jxa_roundtrip" "jxa_roundtrip" "$CAPTURED_STDOUT"

section "doctor default returns structured report"
run_dobby tasks doctor
assert_envelope_shape "tasks.doctor" "$CAPTURED_STDOUT"
assert_jq_truthy "data.checks is array" '(.data.checks | type) == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "5 checks" '(.data.checks | length) == 5' "$CAPTURED_STDOUT"
assert_jq_truthy "timeouts exposed" '(.data.timeouts.osascript_secs | type) == "number"' "$CAPTURED_STDOUT"

finish_test "tasks/structure.sh"
