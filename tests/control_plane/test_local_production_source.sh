#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
. "$ROOT_DIR/scripts/local-production-source.sh"

mkdir -p "$ROOT_DIR/tmp"
TEST_ROOT="$(mktemp -d "$ROOT_DIR/tmp/agents-local-production-source.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT
REPO="$TEST_ROOT/repo"

git init -q -b main "$REPO"
git -C "$REPO" config user.name Test
git -C "$REPO" config user.email test@example.invalid
printf 'one\n' >"$REPO/file.txt"
git -C "$REPO" add file.txt
git -C "$REPO" commit -q -m one

capture_local_production_source "$REPO" main
EXPECTED_SHA="$LOCAL_PRODUCTION_SOURCE_SHA"
verify_local_production_source "$REPO" main "$EXPECTED_SHA"

printf 'dirty\n' >>"$REPO/file.txt"
if verify_local_production_source "$REPO" main "$EXPECTED_SHA"; then
  printf 'dirty source unexpectedly passed\n' >&2
  exit 1
fi
git -C "$REPO" checkout -q -- file.txt

git -C "$REPO" checkout -q -b feature
if capture_local_production_source "$REPO" main; then
  printf 'wrong branch unexpectedly passed\n' >&2
  exit 1
fi
git -C "$REPO" checkout -q main

printf 'two\n' >>"$REPO/file.txt"
git -C "$REPO" add file.txt
git -C "$REPO" commit -q -m two
if verify_local_production_source "$REPO" main "$EXPECTED_SHA"; then
  printf 'moved revision unexpectedly passed\n' >&2
  exit 1
fi

grep -q 'AGENTS_MANAGED_REPO_CHECK_ROOT' "$ROOT_DIR/scripts/check-fast.sh"
grep -q 'AGENTS_MANAGED_REPO_CHECK_ROOT' "$ROOT_DIR/scripts/check-agent-control-planes.sh"
# shellcheck disable=SC2016
grep -q 'AGENTS_MANAGED_REPO_CHECK_ROOT="$ROOT_DIR"' \
  "$ROOT_DIR/scripts/deploy-control-plane-dashboard.sh"
# shellcheck disable=SC2016
grep -q 'cd "$MACHINE_CONTROL_ROOT"' "$ROOT_DIR/scripts/check-agent-control-planes.sh"
# shellcheck disable=SC2016
grep -q 'cd "$MANAGED_REPO_CHECK_ROOT"' "$ROOT_DIR/scripts/check-fast.sh"

printf '[test-local-production-source] passed\n'
