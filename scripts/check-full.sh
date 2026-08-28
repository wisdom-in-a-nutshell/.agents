#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

scripts/check-fast.sh
scripts/check-agent-control-planes.sh

echo "[check-full] passed"
