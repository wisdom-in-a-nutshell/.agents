#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/pre-compact" \
  "$SKILL_DIR/scripts/hooks/session-end" \
  "$SKILL_DIR/scripts/consolidate-thread"

forbidden_var="DOBBY_INTERNAL_""SIDECAR"
if grep -R "$forbidden_var" "$SKILL_DIR/scripts" "$SKILL_DIR/references" >/dev/null; then
  echo "$forbidden_var should not be part of the current simple design" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
repo="$tmp_dir/repo"
mkdir -p "$repo"
fake_codex="$tmp_dir/fake-codex"
cat >"$fake_codex" <<'PY'
#!/usr/bin/env python3
import sys

if sys.argv[1:] == ["app-server"]:
    sys.exit(0)
sys.exit(1)
PY
chmod +x "$fake_codex"

payload="$tmp_dir/pre-compact-payload.json"
cat >"$payload" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "PreCompact",
  "runtime": "codex",
  "cwd": "$repo",
  "repo_root": "$repo",
  "session_id": "thread-test",
  "turn_id": "turn-test",
  "raw_payload": {
    "thread_id": "thread-test",
    "turn_id": "turn-test"
  }
}
JSON

hook_output="$(DOBBY_CODEX_BIN="$fake_codex" "$SKILL_DIR/scripts/hooks/pre-compact" <"$payload")"
if [[ -n "$hook_output" ]]; then
  echo "pre-compact hook should not write stdout" >&2
  exit 1
fi

job_count="$(find "$repo/tmp/dobby-lifecycle/pre-compact/jobs" -type f | wc -l | tr -d ' ')"
run_count="$(find "$repo/tmp/dobby-lifecycle/pre-compact/runs" -type f | wc -l | tr -d ' ')"
if [[ "$job_count" != "1" || "$run_count" != "1" ]]; then
  echo "pre-compact hook should write one job and one run record" >&2
  exit 1
fi

if ! grep -R '"source_label": "pre-compact"' "$repo/tmp/dobby-lifecycle/pre-compact/jobs" >/dev/null; then
  echo "pre-compact job should label the source" >&2
  exit 1
fi

sidecar_repo="$tmp_dir/sidecar-repo"
mkdir -p "$sidecar_repo"
sidecar_payload="$tmp_dir/pre-compact-sidecar-payload.json"
cat >"$sidecar_payload" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "PreCompact",
  "runtime": "codex",
  "cwd": "$sidecar_repo",
  "repo_root": "$sidecar_repo",
  "session_id": "sidecar-thread-test",
  "turn_id": "sidecar-turn-test",
  "raw_payload": {
    "thread_id": "sidecar-thread-test",
    "turn_id": "sidecar-turn-test"
  }
}
JSON

sidecar_output="$(DOBBY_LIFECYCLE_CONSOLIDATION_SIDECAR=1 DOBBY_CODEX_BIN="$fake_codex" "$SKILL_DIR/scripts/hooks/pre-compact" <"$sidecar_payload")"
if [[ -n "$sidecar_output" ]]; then
  echo "sidecar pre-compact guard should not write stdout" >&2
  exit 1
fi

if [[ -d "$sidecar_repo/tmp/dobby-lifecycle/pre-compact/jobs" ]]; then
  sidecar_job_count="$(find "$sidecar_repo/tmp/dobby-lifecycle/pre-compact/jobs" -type f | wc -l | tr -d ' ')"
else
  sidecar_job_count="0"
fi
sidecar_run_count="$(find "$sidecar_repo/tmp/dobby-lifecycle/pre-compact/runs" -type f | wc -l | tr -d ' ')"
if [[ "$sidecar_job_count" != "0" || "$sidecar_run_count" != "1" ]]; then
  echo "sidecar pre-compact guard should write one skipped run and no job" >&2
  exit 1
fi

if ! grep -R '"reason": "consolidation sidecar"' "$sidecar_repo/tmp/dobby-lifecycle/pre-compact/runs" >/dev/null; then
  echo "sidecar pre-compact guard should record skip reason" >&2
  exit 1
fi
