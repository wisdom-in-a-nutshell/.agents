#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/write_journal_entry.py" \
  "$SKILL_DIR/scripts/read_journal_entries.py" \
  "$SKILL_DIR/scripts/validate"
workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
mkdir -p "$workspace/journal/daily/2026-05-29"
cat >"$workspace/journal/daily/2026-05-29/morning.json" <<'JSON'
{
  "agent": "test",
  "date": "2026-05-29",
  "kind": "morning",
  "tz": "Europe/Berlin",
  "captured_at": "2026-05-29T08:00:00+02:00",
  "sleep": {"score_10": 7},
  "energy": {"score_10": 6},
  "mood": {"score_10": 7},
  "grateful": ["one", "two", "three"],
  "one_thing_that_matters": "Protect deep work."
}
JSON
"$SKILL_DIR/scripts/validate" --workspace-root "$workspace" journal/daily/2026-05-29/morning.json --no-input >/dev/null
