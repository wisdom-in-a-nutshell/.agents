#!/usr/bin/env bash
# Fast checks for the shared Dobby workspace shape linter.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile "$SKILL_DIR/scripts/frontmatter.py" "$SKILL_DIR/scripts/lint-workspace" "$SKILL_DIR/scripts/validate"

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

cat >"$workspace/dobby/constitution.md" <<'MD'
---
schemaVersion: 2
kind: dobby-constitution
updatedAt: 2026-05-29T08:00:00+02:00
sensitivity: personal
---
# Dobby Constitution

## Identity and mission

### Identity
Test.

## Operating contract

### Contract
Test.

## Permissions and boundaries

### Boundary
Test.

## Memory and continuity

### Memory
Test.

## Self-evolution

### Evolution
Test.
MD

cat >"$workspace/dobby/growth.jsonl" <<JSONL
{"schemaVersion":1,"kind":"behavioral-correction","id":"growth-test","createdAt":"2026-05-29T08:00:00+02:00","title":"Test","body":"Test","status":"open","source":{"type":"review","ref":"tests/run.sh"}}
JSONL

cat >"$workspace/memory/profile.md" <<'MD'
---
schemaVersion: 2
kind: person-profile
updatedAt: 2026-05-29T08:00:00+02:00
sensitivity: personal
personId: test
personDisplayName: Test
---
# Test Profile

## Identity

### Identity
Test.

## Preferences

## Values

## Patterns

## Life context
MD

cat >"$workspace/memory/now.md" <<'MD'
---
schemaVersion: 2
kind: current-orientation
updatedAt: 2026-05-29T08:00:00+02:00
sensitivity: personal
---
# Current orientation

## This week
Test.
MD

mkdir -p "$workspace/memory/areas/test"
cat >"$workspace/memory/areas/test/area.json" <<JSON
{"schemaVersion": 1, "kind": "memory-area", "id": "test", "title": "Test", "description": "Test area.", "sensitivity": "personal", "updatedAt": "2026-05-29T08:00:00+02:00", "canonicalFiles": {"canon": "canon.md", "log": "log.jsonl"}, "dashboard": {"visible": true, "defaultView": "canon"}, "assets": [], "dataDirs": []}
JSON
cat >"$workspace/memory/areas/test/canon.md" <<'MD'
---
schemaVersion: 2
kind: memory-area-canon
updatedAt: 2026-05-29T08:00:00+02:00
sensitivity: personal
areaId: test
---
# Test canon

## Test
Test.
MD
cat >"$workspace/memory/areas/test/log.jsonl" <<JSONL
{"schemaVersion":1,"kind":"test","id":"test-log","createdAt":"2026-05-29T08:00:00+02:00","title":"Test","body":"Test","source":{"type":"review","ref":"tests/run.sh"},"sensitivity":"personal"}
JSONL

ln -s "$SKILL_DIR" "$workspace/.agents/skills/dobby-workspace"
ln -s "$SKILL_DIR/../journal-checkin" "$workspace/.agents/skills/journal-checkin"
ln -s "$SKILL_DIR/../dobby-shelf" "$workspace/.agents/skills/dobby-shelf"

cat >"$workspace/state/shelf.json" <<JSON
{"schemaVersion": 2, "revision": 1, "timezone": "Europe/Berlin", "updatedAt": "2026-05-29T08:00:00.000Z", "items": []}
JSON

cat >"$workspace/journal/daily/2026-05-29/morning.json" <<JSON
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

mkdir -p "$workspace/memory/sessions/2026/05/29-080000"
cat >"$workspace/memory/sessions/2026/05/29-080000/summary.md" <<'MD'
# Test session

Carry this forward.

## Workspace changes

No durable workspace changes were recorded besides this session-memory record.
MD
cat >"$workspace/memory/sessions/2026/05/29-080000/meta.json" <<JSON
{
  "schemaVersion": 4,
  "createdAt": "2026-05-29T08:00:00+02:00",
  "threadId": "test-thread",
  "runtime": "codex",
  "trigger": "test",
  "cwd": "$workspace",
  "tldr": "Carry this forward."
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

# Triviality gate: automatic finalizes of tiny read-only sessions skip the
# memory record; explicit finalizes and substantive sessions always remember.
python3 - "$SKILL_DIR/scripts" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import remember_lib
import transcript_lib


def fake_dialogue(user_turns, tool_counts):
    d = transcript_lib.Dialogue(runtime="claude")
    for i in range(user_turns):
        d.section("user", None).add_text(f"message {i}")
        d.section("agent", None).add_text("reply")
    d.tool_counts = dict(tool_counts)
    return d


def gate(trigger, user_turns, tool_counts, found=True):
    dialogue = fake_dialogue(user_turns, tool_counts)
    remember_lib.transcript_lib = transcript_lib  # ensure import works
    orig_find = transcript_lib.find_raw_transcript
    orig_parse = transcript_lib.parse_raw_transcript
    transcript_lib.find_raw_transcript = lambda r, s: ("/tmp/fake" if found else None)
    transcript_lib.parse_raw_transcript = lambda p, r: dialogue
    try:
        return remember_lib.triviality_skip_reason(
            runtime="claude", session_id="s1", trigger=trigger
        )
    finally:
        transcript_lib.find_raw_transcript = orig_find
        transcript_lib.parse_raw_transcript = orig_parse


assert gate("manual", 1, {}) is None, "manual trigger must always remember"
assert gate("codexclaw-chat-end", 1, {}) is None, "chat-end must always remember"
assert gate("stale-cleanup", 1, {"Read": 2}) is not None, "tiny read-only stale session must skip"
assert gate("codexclaw-idle-expiry", 2, {}) is not None, "tiny idle session must skip"
assert gate("stale-cleanup", 5, {}) is None, "long session must remember"
assert gate("stale-cleanup", 1, {"Edit": 1}) is None, "mutating session must remember"
assert gate("stale-cleanup", 1, {"Bash": 1}) is None, "shell session must remember"
assert gate("stale-cleanup", 1, {}, found=False) is None, "missing transcript must remember"
print("[triviality-gate] passed")
PY

# Body map boot-cut contract: the marker must exist, the routing table must sit
# above it (boots), and the validation contract below it (on-demand reference).
body_map="$SKILL_DIR/references/body-map.md"
if ! grep -q '<!-- boot-cut -->' "$body_map"; then
  echo "body-map.md is missing the <!-- boot-cut --> marker" >&2
  exit 1
fi
above_cut="$(sed '/<!-- boot-cut -->/q' "$body_map")"
if ! grep -q '## Routing table' <<<"$above_cut"; then
  echo "body-map.md routing table must be above the boot-cut marker" >&2
  exit 1
fi
if grep -q '## Validation contract' <<<"$above_cut"; then
  echo "body-map.md validation contract must be below the boot-cut marker" >&2
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
