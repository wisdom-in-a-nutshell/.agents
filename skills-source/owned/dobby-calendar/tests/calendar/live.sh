#!/usr/bin/env bash
# Live round-trip test for `dobby-calendar add-event` through the bridge.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0
TITLE="DOBBY-TEST-CALENDAR-LIVE-$(date +%s)"
FROM="2026-01-01"
TO="2026-01-03"

cleanup_calendar_event() {
    local ids
    ids=$("$DOBBY_CALENDAR" search "$TITLE" --from "$FROM" --to "$TO" 2>/dev/null \
        | jq -r '.data.events[]?.id' 2>/dev/null || true)
    for id in $ids; do
        [[ -z "$id" ]] && continue
        "$HOME/Applications/Dobby Calendar Bridge.app/Contents/MacOS/DobbyCalendarBridge" send delete --id "$id" >/dev/null 2>&1 || true
    done
}
trap cleanup_calendar_event EXIT

section "add-event actual create returns Dobby envelope"
run_dobby calendar add-event --title "$TITLE" --start "$FROM" --end "2026-01-02" --all-day --no-alert
assert_exit "add-event exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.add-event actual" "$CAPTURED_STDOUT"
assert_jq_eq "created true" '.data.created' "true" "$CAPTURED_STDOUT"
assert_jq_truthy "event payload has title" '.data.event.title == "'"$TITLE"'"' "$CAPTURED_STDOUT"

section "created event can be found and cleaned up"
run_dobby calendar search "$TITLE" --from "$FROM" --to "$TO"
assert_exit "search exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "calendar.search live event" "$CAPTURED_STDOUT"
assert_jq_truthy "found live event" '.data.count >= 1' "$CAPTURED_STDOUT"

finish_test "calendar/live.sh"
