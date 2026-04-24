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
if ! printf '%s' "$CAPTURED_STDOUT" | jq -e '
    (.data.checks // [] | map({(.name): .ok}) | add) as $checks
    | ($checks.things3_running == true)
      and ($checks.sqlite_read_backend == true)
      and ($checks.auth_token_file == true)
' >/dev/null 2>&1; then
    printf "\033[33mSKIP tasks/live.sh — Things 3 URL/SQLite path not healthy enough\033[0m\n"
    exit 0
fi

PREFIX="DOBBY-TEST-$(date +%s)"
CREATED_NAMES=()

cleanup() {
    for name in "${CREATED_NAMES[@]}"; do
        "$DOBBY" tasks cancel "$name" > /dev/null 2>&1 || true
    done
}
trap cleanup EXIT

section "add a task (JSON default)"
run_dobby tasks add "$PREFIX alpha" --when today
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.add alpha" "$CAPTURED_STDOUT"
assert_jq_eq "title echoed" '.data.title' "$PREFIX alpha" "$CAPTURED_STDOUT"
CREATED_NAMES+=("$PREFIX alpha")
sleep 1  # let URL scheme settle

section "add a second task (--json)"
run_dobby tasks add "$PREFIX beta" --when today --notes "test notes" --tags "urgent" --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.add beta" "$CAPTURED_STDOUT"
assert_jq_eq "title echoed" '.data.title' "$PREFIX beta" "$CAPTURED_STDOUT"
CREATED_NAMES+=("$PREFIX beta")
sleep 1

section "add with natural-language --when"
run_dobby tasks add "$PREFIX natural language" --when "tomorrow"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.add natural-language" "$CAPTURED_STDOUT"
assert_jq_eq "title echoed" '.data.title' "$PREFIX natural language" "$CAPTURED_STDOUT"
CREATED_NAMES+=("$PREFIX natural language")
sleep 1

section "today contains the tasks"
run_dobby tasks today
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.today default" "$CAPTURED_STDOUT"
assert_jq_truthy "alpha in today" '.data.tasks | any(.name == "'"$PREFIX alpha"'")' "$CAPTURED_STDOUT"
assert_jq_truthy "beta in today" '.data.tasks | any(.name == "'"$PREFIX beta"'")' "$CAPTURED_STDOUT"

section "today --json returns structured list"
run_dobby tasks today --json
assert_envelope_ok "tasks.today" "$CAPTURED_STDOUT"
assert_jq_truthy "count >= 2" '.data.count >= 2' "$CAPTURED_STDOUT"

section "search finds both"
run_dobby tasks search "$PREFIX" --json
assert_envelope_ok "tasks.search" "$CAPTURED_STDOUT"
assert_jq_truthy "count >= 3" '.data.count >= 3' "$CAPTURED_STDOUT"

section "cancel beta"
run_dobby tasks cancel "$PREFIX beta"
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.cancel beta" "$CAPTURED_STDOUT"
assert_jq_eq "canceled name" '.data.name' "$PREFIX beta" "$CAPTURED_STDOUT"
# Remove beta from cleanup list since it's already canceled.
CREATED_NAMES=("$PREFIX alpha" "$PREFIX natural language")

section "delete without --yes is rejected"
run_dobby tasks delete "anything"
assert_exit "exit 2" 2 "$CAPTURED_EXIT"
assert_envelope_error "tasks.delete no --yes" "E_VALIDATION" "$CAPTURED_STDOUT"

section "cleanup alpha"
run_dobby tasks cancel "$PREFIX alpha"
assert_exit "alpha cleanup exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.cancel alpha" "$CAPTURED_STDOUT"

section "cleanup natural-language task"
run_dobby tasks cancel "$PREFIX natural language"
assert_exit "natural-language cleanup exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "tasks.cancel natural-language" "$CAPTURED_STDOUT"
CREATED_NAMES=()

section "post-cleanup: no open test tasks remain"
run_dobby tasks search "$PREFIX"
assert_envelope_ok "tasks.search cleanup" "$CAPTURED_STDOUT"
assert_jq_eq "no open tasks remain" '.data.count' "0" "$CAPTURED_STDOUT"

section "post-cleanup: completed/canceled lookup remains structured"
run_dobby tasks search "$PREFIX" --include-completed
assert_envelope_ok "tasks.search cleanup include-completed" "$CAPTURED_STDOUT"
assert_jq_truthy "completed/canceled query returns count" '.data.count >= 3' "$CAPTURED_STDOUT"

finish_test "tasks/live.sh"
