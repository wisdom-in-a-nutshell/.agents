#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT/tests/contract.sh"
bash "$ROOT/tests/sqlite.sh"

if [[ "${RUN_LIVE:-0}" == "1" ]]; then
    bash "$ROOT/tests/live.sh"
else
    printf 'skipped things-client live tests; set RUN_LIVE=1 to run real Things write smoke\n'
fi
