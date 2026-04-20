#!/usr/bin/env bash
# Structure tests for Dobby calendar skill scripts.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

section "dobby-calendar --help surface"
run_dobby calendar --help
assert_exit "help exit 0" 0 "$CAPTURED_EXIT"
for cmd in doctor calendars today upcoming week month list search add-event upsert-event; do
    assert_contains "$cmd in help" "$cmd" "$CAPTURED_STDOUT"
done

section "doctor returns envelope"
run_dobby calendar doctor
assert_exit "doctor exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.doctor" "$CAPTURED_STDOUT"
assert_jq_eq "command=calendar.doctor" '.command' "calendar.doctor" "$CAPTURED_STDOUT"
assert_jq_truthy "default calendar set" '.data.default_calendar == "adithyan@wisdominanutshell.academy"' "$CAPTURED_STDOUT"

section "calendars lists default calendar"
run_dobby calendar calendars
assert_exit "calendars exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.calendars" "$CAPTURED_STDOUT"
assert_jq_truthy "has default calendar" '.data.calendars | any(.title == "adithyan@wisdominanutshell.academy")' "$CAPTURED_STDOUT"

section "search requires date range"
run_dobby calendar search Neha
assert_exit "missing range exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "calendar.search missing range" "E_VALIDATION" "$CAPTURED_STDOUT"
assert_contains "usage mentions --from" "--from" "$CAPTURED_STDOUT"
assert_eq "stderr clean on parser error" "" "$CAPTURED_STDERR"

section "date-bounded search returns envelope"
run_dobby calendar search Birthday --from 2026-01-01 --to 2026-12-31
assert_exit "search exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.search" "$CAPTURED_STDOUT"
assert_jq_eq "command=calendar.search" '.command' "calendar.search" "$CAPTURED_STDOUT"
assert_jq_truthy "events array" '(.data.events | type) == "array"' "$CAPTURED_STDOUT"

section "add-event dry-run does not create"
run_dobby calendar add-event --title "DOBBY-TEST-CALENDAR-DRY-RUN" --start 2026-01-01 --end 2026-01-02 --all-day --dry-run
assert_exit "dry-run exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.add-event dry-run" "$CAPTURED_STDOUT"
assert_jq_eq "created false" '.data.created' "false" "$CAPTURED_STDOUT"
assert_jq_eq "dry_run true" '.data.dry_run' "true" "$CAPTURED_STDOUT"

finish_test "calendar/structure.sh"
