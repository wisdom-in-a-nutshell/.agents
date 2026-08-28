#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_HOME=""
HOST_USER_SITE="$(python3 -c 'import site; print(site.getusersitepackages())')"

cleanup() {
  if [[ -n "${TEST_HOME:-}" && -d "$TEST_HOME" ]]; then
    rm -rf "$TEST_HOME"
  fi
}
trap cleanup EXIT

cd "$ROOT_DIR"
mkdir -p "$ROOT_DIR/tmp"
TEST_HOME="$(mktemp -d "$ROOT_DIR/tmp/control-plane-test-home.XXXXXX")"
HOME="$TEST_HOME" PYTHONPATH="${HOST_USER_SITE}${PYTHONPATH:+:${PYTHONPATH}}" \
  python3 -m unittest discover -s tests/control_plane -t . "$@"
