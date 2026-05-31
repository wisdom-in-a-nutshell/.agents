#!/usr/bin/env bash
# Fast checks for the shared Dobby workspace shape linter.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile "$SKILL_DIR/scripts/lint-workspace" "$SKILL_DIR/scripts/validate"

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT

mkdir -p \
  "$workspace/.agents/skills" \
  "$workspace/memory/areas" \
  "$workspace/memory/sessions/2026/05" \
  "$workspace/journal/daily/2026-05-29" \
  "$workspace/journal/monthly" \
  "$workspace/journal/templates" \
  "$workspace/state" \
  "$workspace/dobby" \
  "$workspace/projects" \
  "$workspace/tmp" \
  "$workspace/scripts/hooks" \
  "$workspace/scripts/local"

touch \
  "$workspace/scripts/check-fast.sh" \
  "$workspace/scripts/check-full.sh" \
  "$workspace/scripts/lint-workspace.py"


cat >"$workspace/dobby/constitution.json" <<JSON
{"schemaVersion": 1, "kind": "dobby-constitution", "updatedAt": "2026-05-29T08:00:00+02:00", "groups": {"identity": {"title": "Identity", "sections": {"identity": {"title": "Identity", "level": 2, "body": "Test"}}}, "operating": {"title": "Operating", "sections": {}}, "boundaries": {"title": "Boundaries", "sections": {}}, "memory_policy": {"title": "Memory policy", "sections": {}}, "self_evolution": {"title": "Self evolution", "sections": {}}}, "migratedFrom": "test"}
JSON

cat >"$workspace/dobby/growth.jsonl" <<JSONL
{"schemaVersion":1,"kind":"test","id":"growth-test","createdAt":"2026-05-29T08:00:00+02:00","title":"Test","body":"Test","status":"open","source":{"type":"test","ref":"tests/run.sh"}}
JSONL

cat >"$workspace/memory/profile.json" <<JSON
{"schemaVersion": 1, "kind": "person-profile", "updatedAt": "2026-05-29T08:00:00+02:00", "person": {"id": "test", "displayName": "Test"}, "groups": {"identity": {"title": "Identity", "sections": {"identity": {"title": "Identity", "level": 2, "body": "Test", "sensitivity": "personal"}}}, "preferences": {"title": "Preferences", "sections": {}}, "values": {"title": "Values", "sections": {}}, "patterns": {"title": "Patterns", "sections": {}}, "life_context": {"title": "Life context", "sections": {}}}, "migratedFrom": "test"}
JSON

cat >"$workspace/memory/now.json" <<JSON
{"schemaVersion": 1, "kind": "current-orientation", "updatedAt": "2026-05-29T08:00:00+02:00", "title": "Current orientation", "body": "Test", "sections": {"this_week": {"title": "This week", "level": 2, "body": "Test"}}, "migratedFrom": "test"}
JSON

mkdir -p "$workspace/memory/areas/test"
cat >"$workspace/memory/areas/test/area.json" <<JSON
{"schemaVersion": 1, "kind": "memory-area", "id": "test", "title": "Test", "description": "Test area.", "sensitivity": "personal", "updatedAt": "2026-05-29T08:00:00+02:00", "canonicalFiles": {"canon": "canon.json", "log": "log.jsonl"}, "dashboard": {"visible": true, "defaultView": "canon"}, "assets": [], "dataDirs": []}
JSON
cat >"$workspace/memory/areas/test/canon.json" <<JSON
{"schemaVersion": 1, "kind": "memory-area-canon", "areaId": "test", "updatedAt": "2026-05-29T08:00:00+02:00", "sections": {"test": {"title": "Test", "body": "Test", "sensitivity": "personal"}}}
JSON
cat >"$workspace/memory/areas/test/log.jsonl" <<JSONL
{"schemaVersion":1,"kind":"test","id":"test-log","createdAt":"2026-05-29T08:00:00+02:00","title":"Test","body":"Test","source":{"type":"test","ref":"tests/run.sh"},"sensitivity":"personal"}
JSONL

ln -s "$SKILL_DIR" "$workspace/.agents/skills/dobby-workspace"
ln -s "$SKILL_DIR/../dobby-lifecycle" "$workspace/.agents/skills/dobby-lifecycle"
ln -s "$SKILL_DIR/../journal-checkin" "$workspace/.agents/skills/journal-checkin"
ln -s "$SKILL_DIR/../dobby-shelf" "$workspace/.agents/skills/dobby-shelf"

cat >"$workspace/state/shelf.json" <<JSON
{"schemaVersion": 1, "revision": 1, "updatedAt": "2026-05-29T08:00:00.000Z", "items": []}
JSON

cat >"$workspace/journal/daily/2026-05-29/morning.json" <<JSON
{
  "agent": "test",
  "date": "2026-05-29",
  "kind": "morning",
  "tz": "Europe/Berlin",
  "captured_at": "2026-05-29T08:00:00+02:00",
  "source": "test",
  "sleep": {"score_10": 7},
  "energy": {"score_10": 6},
  "mood": {"score_10": 7},
  "grateful": ["one", "two", "three"],
  "one_thing_that_matters": "Protect deep work."
}
JSON

cat >"$workspace/memory/sessions/2026/05/29-080000.json" <<JSON
{
  "schemaVersion": 2,
  "createdAt": "2026-05-29T08:00:00+02:00",
  "threadId": "test-thread",
  "trigger": "test",
  "title": "Test session",
  "summary": "Carry this forward.",
  "workspaceChanges": "No durable workspace changes were recorded besides this session-memory record."
}
JSON

"$SKILL_DIR/scripts/lint-workspace" --workspace-root "$workspace"

git -C "$workspace" init -q
git -C "$workspace" add .
"$SKILL_DIR/scripts/validate" --workspace-root "$workspace" --scope staged --no-input

morning="$workspace/journal/daily/2026-05-29/morning.json"
cp "$morning" "$workspace/tmp/morning-valid.json"
python3 - "$morning" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text())
data.pop("captured_at", None)
path.write_text(json.dumps(data, indent=2) + "\n")
PY
git -C "$workspace" add journal/daily/2026-05-29/morning.json
cp "$workspace/tmp/morning-valid.json" "$morning"
if "$SKILL_DIR/scripts/validate" --workspace-root "$workspace" --scope staged --no-input >/tmp/dobby-workspace-staged-mismatch.out 2>&1; then
  echo "expected validator to reject staged paths that also have unstaged worktree changes" >&2
  exit 1
fi
if ! grep -q 'unstaged changes' /tmp/dobby-workspace-staged-mismatch.out; then
  echo "expected staged/worktree mismatch failure to mention unstaged changes" >&2
  cat /tmp/dobby-workspace-staged-mismatch.out >&2
  exit 1
fi

touch "$workspace/STRUCTURE.md"
if "$SKILL_DIR/scripts/lint-workspace" --workspace-root "$workspace" >/tmp/dobby-workspace-lint-test.out 2>&1; then
  echo "expected linter to reject STRUCTURE.md" >&2
  exit 1
fi
if ! grep -q 'STRUCTURE.md' /tmp/dobby-workspace-lint-test.out; then
  echo "expected unexpected STRUCTURE.md failure to mention STRUCTURE.md" >&2
  cat /tmp/dobby-workspace-lint-test.out >&2
  exit 1
fi
