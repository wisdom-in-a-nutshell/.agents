#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
mkdir -p "$workspace/state"
cat >"$workspace/state/shelf.json" <<'JSON'
{
  "schemaVersion": 1,
  "revision": 1,
  "updatedAt": "2026-05-29T08:00:00.000Z",
  "items": [
    {
      "id": "buy-oats",
      "title": "Buy oats",
      "kind": "buy",
      "status": "open",
      "source": {"type": "agent", "ref": "test"},
      "deferCount": 0,
      "createdAt": "2026-05-29T08:00:00.000Z",
      "updatedAt": "2026-05-29T08:00:00.000Z"
    }
  ]
}
JSON
"$SKILL_DIR/scripts/validate" --workspace-root "$workspace" state/shelf.json --no-input >/dev/null
python3 -m py_compile "$SKILL_DIR/scripts/validate"
