#!/usr/bin/env bash
# Top-level test runner for the Dobby skill scripts.
#
# By default, runs only cheap/non-mutating suites. Live suites (`*/live.sh`)
# are opt-in because they may write to real local surfaces such as Things 3 or
# Calendar before cleaning up.
#
# When the Things 3 live suite is selected, sweeps DOBBY-TEST-* leftover tasks
# before and after the run so aborted live runs do not pollute the user's task
# surface. Cheap/default runs do not touch Things for sweeping.
#
# Usage:
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh                 # cheap suites only
#     RUN_LIVE=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh      # include all live suites
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh memory          # only memory suites
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh tasks live      # only tasks/live.sh
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh live            # all live suites
#     SKIP_LIVE=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh     # force-skip live suites
#     SWEEP_THINGS=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh  # cleanup stale DOBBY-TEST-* tasks
#     SKIP_SWEEP=1 RUN_LIVE=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh # skip live sweep
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$TESTS_DIR/.." && pwd)"
DOBBY_BIN="$TESTS_DIR/support/dobby-shim"
REPO_ROOT="${DOBBY_WORKSPACE:-/Users/adi/GitHub/adi}"
export DOBBY_WORKSPACE="$REPO_ROOT"

# Sweep any stale Things 3 test artifacts.
sweep_things3() {
    [[ "${SKIP_SWEEP:-0}" == "1" ]] && return 0
    # Uses the Dobby CLI itself (AppleScript-backed) — no external task binary.
    local found=0
    local ids
    ids=$("$DOBBY_BIN" tasks search "DOBBY-TEST-" --include-completed --json 2>/dev/null \
        | jq -r '.data.tasks[]?.id' 2>/dev/null || true)
    for id in $ids; do
        [[ -z "$id" ]] && continue
        "$DOBBY_BIN" tasks delete "$id" --yes > /dev/null 2>&1 || true
        found=$((found + 1))
    done
    if (( found > 0 )); then
        printf "\033[33m[sweep] removed %d stale DOBBY-TEST-* artifacts\033[0m\n" "$found"
    fi
}

has_filter() {
    local needle="$1"
    shift || true
    local pattern
    for pattern in "$@"; do
        [[ "$pattern" == *"$needle"* ]] && return 0
    done
    return 1
}

matches_filters() {
    local file="$1"
    shift || true
    local pattern
    for pattern in "$@"; do
        [[ "$file" == *"$pattern"* ]] || return 1
    done
    return 0
}

# Collect test scripts. If args are given, each arg is an ANDed substring filter
# on the script path. Example: `tasks live` selects `tasks/live.sh`.
SCRIPTS=()
SKIPPED_LIVE=0
LIVE_FILTER_REQUESTED=0
if has_filter "live" "$@"; then
    LIVE_FILTER_REQUESTED=1
fi
while IFS= read -r -d '' file; do
    # Skip library shims
    [[ "$file" == */lib/* ]] && continue
    [[ "$(basename "$file")" == "run.sh" ]] && continue
    if [[ $# -gt 0 ]]; then
        matches_filters "$file" "$@" || continue
    fi
    # Honor SKIP_LIVE. Otherwise, live suites are opt-in via RUN_LIVE=1 or an
    # explicit `live` filter.
    if [[ "${SKIP_LIVE:-0}" == "1" ]] && [[ "$file" == *"/live.sh" ]]; then
        continue
    fi
    if [[ "$file" == *"/live.sh" ]] \
        && [[ "${RUN_LIVE:-0}" != "1" ]] \
        && [[ "$LIVE_FILTER_REQUESTED" != "1" ]]; then
        SKIPPED_LIVE=$((SKIPPED_LIVE + 1))
        continue
    fi
    # Honor SKIP_TASKS (when Things 3 isn't available)
    if [[ "${SKIP_TASKS:-0}" == "1" ]] && [[ "$file" == */tasks/* ]]; then
        continue
    fi
    SCRIPTS+=("$file")
done < <(find "$TESTS_DIR" -type f -name '*.sh' -print0 | sort -z)

SELECTED_TASKS_LIVE=0
for script in "${SCRIPTS[@]}"; do
    if [[ "$script" == */tasks/live.sh ]]; then
        SELECTED_TASKS_LIVE=1
        break
    fi
done

if [[ "$SKIPPED_LIVE" -gt 0 ]]; then
    printf "\033[33m[tests] skipped %d live suite(s); set RUN_LIVE=1 or filter on 'live' to run them\033[0m\n" "$SKIPPED_LIVE"
fi

if [[ "$SELECTED_TASKS_LIVE" == "1" || "${SWEEP_THINGS:-0}" == "1" ]]; then
    sweep_things3
fi

TOTAL_SUITES=0
FAILED_SUITES=0
FAILED_NAMES=()

print_header() {
    printf "\n\033[1m════════════════════════════════════════\033[0m\n"
    printf "\033[1m%s\033[0m\n" "$1"
    printf "\033[1m════════════════════════════════════════\033[0m\n"
}

for script in "${SCRIPTS[@]}"; do
    rel="${script#$SKILL_DIR/}"
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    print_header "$rel"
    if bash "$script"; then
        :
    else
        rc=$?
        FAILED_SUITES=$((FAILED_SUITES + 1))
        FAILED_NAMES+=("$rel ($rc failures)")
    fi
done

if [[ "$SELECTED_TASKS_LIVE" == "1" || "${SWEEP_THINGS:-0}" == "1" ]]; then
    sweep_things3  # post-run sweep, catches anything the individual trap cleanups missed
fi

printf "\n\033[1m════════════════════════════════════════\033[0m\n"
if [[ $FAILED_SUITES -eq 0 ]]; then
    printf "\033[32m✓ %d/%d suite(s) passed\033[0m\n" "$TOTAL_SUITES" "$TOTAL_SUITES"
    exit 0
else
    printf "\033[31m✗ %d/%d suite(s) failed\033[0m\n" "$FAILED_SUITES" "$TOTAL_SUITES"
    for name in "${FAILED_NAMES[@]}"; do
        printf "  - %s\n" "$name"
    done
    exit 1
fi
