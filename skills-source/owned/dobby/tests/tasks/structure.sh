#!/usr/bin/env bash
# Structure tests for `dobby tasks` (AppleScript backend).
#
# Tests argparse surface, validation errors, read-only snapshots, and doctor.
# This suite must not create/edit/delete real Things tasks. Write-path coverage
# belongs in tasks/live.sh, which is opt-in from tests/run.sh.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

section "dobby tasks --help surface"
run_dobby tasks --help
assert_exit "help exit 0" 0 "$CAPTURED_EXIT"
for cmd in today inbox upcoming anytime someday logbook snapshot overdue search inspect projects areas tags add done cancel schedule edit delete project-new area-new doctor; do
    assert_contains "$cmd in help" "$cmd" "$CAPTURED_STDOUT"
done

section "snapshot returns today/overdue/inbox in one envelope"
run_dobby tasks snapshot
assert_exit "snapshot exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.snapshot" "$CAPTURED_STDOUT"
assert_jq_truthy "has today view" '.data.views.today.tasks | type == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "has overdue view" '.data.views.overdue.tasks | type == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "has inbox view" '.data.views.inbox.tasks | type == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "backend exposed" '.data.backend.name == "sqlite" or .data.backend.name == "jxa"' "$CAPTURED_STDOUT"

section "minimal snapshot limits returned tasks while keeping counts"
run_dobby tasks snapshot --minimal --limit 2
assert_exit "minimal snapshot exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.snapshot minimal" "$CAPTURED_STDOUT"
assert_jq_truthy "minimal flag exposed" '.data.minimal == true' "$CAPTURED_STDOUT"
assert_jq_truthy "limit exposed" '.data.limit == 2' "$CAPTURED_STDOUT"
assert_jq_truthy "today limited" '(.data.views.today.tasks | length) <= 2' "$CAPTURED_STDOUT"
assert_jq_truthy "overdue limited" '(.data.views.overdue.tasks | length) <= 2' "$CAPTURED_STDOUT"
assert_jq_truthy "inbox limited" '(.data.views.inbox.tasks | length) <= 2' "$CAPTURED_STDOUT"

section "inspect resolves a project through the read backend"
run_dobby tasks projects
assert_exit "projects exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.projects" "$CAPTURED_STDOUT"
FIRST_PROJECT=$(printf '%s' "$CAPTURED_STDOUT" | jq -r '.data.projects[0].name // empty')
if [[ -n "$FIRST_PROJECT" ]]; then
    run_dobby tasks inspect "$FIRST_PROJECT"
    assert_exit "inspect exit 0" 0 "$CAPTURED_EXIT"
    assert_envelope_ok "tasks.inspect" "$CAPTURED_STDOUT"
    assert_jq_eq "inspect returns project" '.data.result.type' "project" "$CAPTURED_STDOUT"
    assert_jq_truthy "inspect includes items array" '.data.result.items | type == "array"' "$CAPTURED_STDOUT"
fi

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
if [[ "$CAPTURED_EXIT" -eq 0 || "$CAPTURED_EXIT" -eq 4 ]]; then
    _pass "exit 0 or 4"
else
    _fail "exit 0 or 4" "expected exit 0 or 4, got $CAPTURED_EXIT"
fi
assert_contains "doctor checks osascript" "osascript" "$CAPTURED_STDOUT"
assert_contains "doctor checks things3_installed" "things3_installed" "$CAPTURED_STDOUT"
assert_contains "doctor checks things3_running" "things3_running" "$CAPTURED_STDOUT"
assert_contains "doctor checks sqlite backend" "sqlite_read_backend" "$CAPTURED_STDOUT"
assert_contains "doctor checks jxa_roundtrip" "jxa_roundtrip" "$CAPTURED_STDOUT"
assert_contains "doctor checks AppleScript task access" "applescript_task_access" "$CAPTURED_STDOUT"

section "doctor default returns structured report"
run_dobby tasks doctor
assert_envelope_shape "tasks.doctor" "$CAPTURED_STDOUT"
assert_jq_truthy "data.checks is array" '(.data.checks | type) == "array"' "$CAPTURED_STDOUT"
assert_jq_truthy "at least 6 checks" '(.data.checks | length) >= 6' "$CAPTURED_STDOUT"
assert_jq_truthy "timeouts exposed" '(.data.timeouts.osascript_secs | type) == "number"' "$CAPTURED_STDOUT"
assert_jq_truthy "read backend exposed" '.data.read_backend == "auto" or .data.read_backend == "sqlite" or .data.read_backend == "jxa"' "$CAPTURED_STDOUT"

finish_test "tasks/structure.sh"
