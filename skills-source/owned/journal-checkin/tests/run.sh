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

cat >"$workspace/payload.json" <<'JSON'
{
  "sleep": {"score_10": 8},
  "energy": {"score_10": 7},
  "mood": {"score_10": 8},
  "grateful": ["one", "two", "three"],
  "one_thing_that_matters": "Keep the morning simple.",
  "implementation_next_step": "This should not be stored.",
  "show_up_as": "This should not be stored."
}
JSON
"$SKILL_DIR/scripts/write_journal_entry.py" \
  --workspace-root "$workspace" \
  --kind morning \
  --date 2026-05-30 \
  --payload-file "$workspace/payload.json" >/dev/null
"$SKILL_DIR/scripts/validate" --workspace-root "$workspace" journal/daily/2026-05-30/morning.json --no-input >/dev/null
python3 - "$workspace/journal/daily/2026-05-30/morning.json" <<'PY'
import json
import sys

entry = json.loads(open(sys.argv[1], encoding="utf-8").read())
for removed in ("implementation_next_step", "show_up_as"):
    if removed in entry:
        raise SystemExit(f"{removed} should not be stored in morning entries")
PY
