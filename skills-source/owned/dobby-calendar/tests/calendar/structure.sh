#!/usr/bin/env bash
# Structure tests for Dobby calendar skill scripts.
# These stay non-mutating and tolerate local Calendar permission differences.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0
# Calendar writes need a target for dry-run shaping. Override when needed.
export DOBBY_CALENDAR_DEFAULT="${DOBBY_CALENDAR_DEFAULT:-Work}"

section "dobby-calendar --help surface"
run_dobby calendar --help
assert_exit "help exit 0" 0 "$CAPTURED_EXIT"
for cmd in doctor calendars today upcoming week month list search add-event upsert-event; do
    assert_contains "$cmd in help" "$cmd" "$CAPTURED_STDOUT"
done

section "doctor returns a stable envelope"
run_dobby calendar doctor
if [[ "$CAPTURED_EXIT" -eq 0 || "$CAPTURED_EXIT" -eq 3 || "$CAPTURED_EXIT" -eq 4 ]]; then
    _pass "doctor exit is stable/auth-aware"
else
    _fail "doctor exit is stable/auth-aware" "expected 0, 3, or 4; got $CAPTURED_EXIT"
fi
assert_envelope_shape "calendar.doctor" "$CAPTURED_STDOUT"
assert_jq_eq "command=calendar.doctor" '.command' "calendar.doctor" "$CAPTURED_STDOUT"
assert_jq_eq "default calendar echoed" '.data.default_calendar' "$DOBBY_CALENDAR_DEFAULT" "$CAPTURED_STDOUT"

section "calendars returns a stable envelope"
run_dobby calendar calendars
assert_exit "calendars exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.calendars" "$CAPTURED_STDOUT"
assert_jq_truthy "calendars array" '(.data.calendars | type) == "array"' "$CAPTURED_STDOUT"

section "search requires date range"
run_dobby calendar search Neha
assert_exit "missing range exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "calendar.search missing range" "E_VALIDATION" "$CAPTURED_STDOUT"
assert_contains "usage mentions --from" "--from" "$CAPTURED_STDOUT"
assert_eq "stderr clean on parser error" "" "$CAPTURED_STDERR"

section "date-bounded search returns a stable envelope"
run_dobby calendar search Birthday --from 2026-01-01 --to 2026-12-31
if [[ "$CAPTURED_EXIT" -eq 0 ]]; then
    assert_envelope_ok "calendar.search" "$CAPTURED_STDOUT"
    assert_jq_truthy "events array" '(.data.events | type) == "array"' "$CAPTURED_STDOUT"
elif [[ "$CAPTURED_EXIT" -eq 1 ]]; then
    assert_envelope_error "calendar.search not found" "E_NOT_FOUND" "$CAPTURED_STDOUT"
elif [[ "$CAPTURED_EXIT" -eq 3 ]]; then
    assert_envelope_error "calendar.search auth" "E_AUTH" "$CAPTURED_STDOUT"
else
    _fail "search exit is success, not-found, or auth failure" "expected 0, 1, or 3; got $CAPTURED_EXIT"
    assert_envelope_shape "calendar.search" "$CAPTURED_STDOUT"
fi
assert_jq_eq "command=calendar.search" '.command' "calendar.search" "$CAPTURED_STDOUT"

section "add-event dry-run does not create"
run_dobby calendar add-event --title "DOBBY-TEST-CALENDAR-DRY-RUN" --start 2026-01-01 --end 2026-01-02 --all-day --dry-run
assert_exit "dry-run exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.add-event dry-run" "$CAPTURED_STDOUT"
assert_jq_eq "created false" '.data.created' "false" "$CAPTURED_STDOUT"
assert_jq_eq "dry_run true" '.data.dry_run' "true" "$CAPTURED_STDOUT"

finish_test "calendar/structure.sh"
