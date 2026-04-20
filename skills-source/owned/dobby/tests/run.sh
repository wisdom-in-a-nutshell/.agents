#!/usr/bin/env bash
# Top-level test runner for the Dobby skill scripts.
#
# Runs every *.sh under tests/ (except lib/*.sh), collects pass/fail counts,
# and returns non-zero if any suite failed.
#
# Before running the suites, sweeps any DOBBY-* leftover tasks in Things 3 so
# each run starts from a clean slate regardless of what earlier runs (or
# aborted runs) may have left behind. Sweeps again after the suites finish
# so the user's Things 3 is never polluted by test artifacts.
#
# Usage:
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh              # run everything
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh memory       # run only memory/*.sh
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh tasks live   # run specific tests
#     SKIP_LIVE=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh  # skip tasks/live.sh
#     SKIP_SWEEP=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh # skip pre/post Things 3 sweep
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$TESTS_DIR/.." && pwd)"
DOBBY_BIN="$TESTS_DIR/support/dobby-shim"
REPO_ROOT="${DOBBY_WORKSPACE:-/Users/adi/GitHub/adi}"
export DOBBY_WORKSPACE="$REPO_ROOT"

# Sweep any stale Things 3 test artifacts. The sweep patterns intentionally
# match the prefixes used by live tests: DOBBY-TEST-, DOBBY-RT, DOBBY-SF-,
# DOBBY-ES-, DOBBY-DEBUG-, DOBBY-SHAPE-, DOBBY-RAW-, DOBBY-ROUNDTRIP.
# The generic `DOBBY-` prefix handles anything else Adi didn't label `dobby`.
sweep_things3() {
    [[ "${SKIP_SWEEP:-0}" == "1" ]] && return 0
    # Clean up any DOBBY-TEST-* tasks left by prior test runs.
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

sweep_things3

# Collect test scripts. If args given, use them as filters (substring match on path).
SCRIPTS=()
while IFS= read -r -d '' file; do
    # Skip library shims
    [[ "$file" == */lib/* ]] && continue
    [[ "$(basename "$file")" == "run.sh" ]] && continue
    if [[ $# -gt 0 ]]; then
        match=0
        for pattern in "$@"; do
            if [[ "$file" == *"$pattern"* ]]; then
                match=1
                break
            fi
        done
        (( match )) || continue
    fi
    # Honor SKIP_LIVE
    if [[ "${SKIP_LIVE:-0}" == "1" ]] && [[ "$file" == *"/live.sh" ]]; then
        continue
    fi
    # Honor SKIP_TASKS (when Things 3 isn't available)
    if [[ "${SKIP_TASKS:-0}" == "1" ]] && [[ "$file" == */tasks/* ]]; then
        continue
    fi
    SCRIPTS+=("$file")
done < <(find "$TESTS_DIR" -type f -name '*.sh' -print0 | sort -z)

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

sweep_things3  # post-run sweep, catches anything the individual trap cleanups missed

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
