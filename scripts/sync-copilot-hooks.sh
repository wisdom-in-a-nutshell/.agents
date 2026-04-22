#!/usr/bin/env bash
set -euo pipefail

APPLY=0
CHECK=0
REGISTRY_FILE=""
HOOKS_REGISTRY_FILE=""
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_REGISTRY_FILE="${ROOT_DIR}/codex/config/repo-bootstrap.json"
DEFAULT_HOOKS_REGISTRY_FILE="${ROOT_DIR}/hooks/registry.json"
TARGET_RELATIVE=".github/hooks/agent-control-plane.json"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed repo-local GitHub Copilot hook files from the canonical registry.
Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                 Apply changes in place
  --dry-run               Show diffs only (default)
  --check                 Fail if rendered files differ from repo-local files
  --registry <path>       Override repo bootstrap registry
                          (default: codex/config/repo-bootstrap.json)
  --hooks-registry <path> Override shared hooks registry
                          (default: hooks/registry.json)
  --repo <path>           Limit sync/check to an exact repo path (repeatable)
  -h, --help              Show this help

Examples:
  ~/.agents/scripts/sync-copilot-hooks.sh
  ~/.agents/scripts/sync-copilot-hooks.sh --apply
  ~/.agents/scripts/sync-copilot-hooks.sh --check --repo ~/GitHub/win
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${TMP_DIR:-}" && -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}
trap cleanup EXIT

TMP_DIR="$(mktemp -d)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      CHECK=0
      shift
      ;;
    --dry-run)
      APPLY=0
      CHECK=0
      shift
      ;;
    --check)
      APPLY=0
      CHECK=1
      shift
      ;;
    --registry)
      REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --hooks-registry)
      HOOKS_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_FILTERS+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

if [[ -z "$REGISTRY_FILE" ]]; then
  REGISTRY_FILE="$DEFAULT_REGISTRY_FILE"
fi
if [[ -z "$HOOKS_REGISTRY_FILE" ]]; then
  HOOKS_REGISTRY_FILE="$DEFAULT_HOOKS_REGISTRY_FILE"
fi

REGISTRY_FILE="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$REGISTRY_FILE")"
HOOKS_REGISTRY_FILE="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$HOOKS_REGISTRY_FILE")"

[[ -f "$REGISTRY_FILE" ]] || die "Missing registry file: $REGISTRY_FILE"
[[ -r "$REGISTRY_FILE" ]] || die "Registry file is not readable: $REGISTRY_FILE"
[[ -f "$HOOKS_REGISTRY_FILE" ]] || die "Missing hooks registry file: $HOOKS_REGISTRY_FILE"
[[ -r "$HOOKS_REGISTRY_FILE" ]] || die "Hooks registry file is not readable: $HOOKS_REGISTRY_FILE"

ensure_parent_dir() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
}

show_diff() {
  local original="$1"
  local rendered="$2"
  if [[ -f "$original" ]]; then
    diff -u "$original" "$rendered" || true
  else
    diff -u /dev/null "$rendered" || true
  fi
}

install_rendered_file() {
  local rendered="$1"
  local target="$2"
  local mode="644"

  if [[ -f "$target" ]] && cmp -s "$target" "$rendered"; then
    log "No change: $target"
    return 0
  fi

  if [[ -f "$target" ]]; then
    mode="$(stat -f "%Lp" "$target" 2>/dev/null || echo 644)"
  fi

  install -m "$mode" "$rendered" "$target"
  log "Updated: $target"
}

is_drifted() {
  local target="$1"
  local rendered="$2"

  [[ ! -f "$target" ]] || ! cmp -s "$target" "$rendered"
}

MANIFEST_FILE="${TMP_DIR}/manifest.tsv"
python3 - "$ROOT_DIR" "$REGISTRY_FILE" "$HOOKS_REGISTRY_FILE" "$TMP_DIR" "$TARGET_RELATIVE" ${REPO_FILTERS[@]+"${REPO_FILTERS[@]}"} >"$MANIFEST_FILE" <<'PY'
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

root_dir = Path(sys.argv[1]).resolve()
registry_path = Path(sys.argv[2]).expanduser().resolve()
hooks_registry_path = Path(sys.argv[3]).expanduser().resolve()
tmp_dir = Path(sys.argv[4]).resolve()
target_relative = Path(sys.argv[5])
filters = {str(Path(value).expanduser().resolve()) for value in sys.argv[6:] if value}

sys.path.insert(0, str(root_dir))

from hooks.control_plane import load_hooks_registry, render_copilot_hooks


data = json.loads(registry_path.read_text(encoding="utf-8"))
repos = data.get("repos", [])
if not isinstance(repos, list):
    raise SystemExit(f"{registry_path}: repos must be an array")

hooks_registry = load_hooks_registry(hooks_registry_path)

manifest_lines: list[str] = []
for item in repos:
    if not isinstance(item, dict):
        continue
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        continue
    repo_path = Path(raw_path).expanduser().resolve()
    try:
        actual_repo = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(f"WARNING: skipping non-git path: {repo_path}", file=sys.stderr)
        continue

    actual_repo_path = Path(actual_repo).resolve()
    actual_repo = str(actual_repo_path)
    repo_name = actual_repo_path.name or actual_repo
    if filters and actual_repo not in filters:
        continue

    rendered_hooks = render_copilot_hooks(hooks_registry, repo_name=repo_name)
    rendered_path = tmp_dir / f"{hashlib.sha256(actual_repo.encode()).hexdigest()}.json"
    rendered_path.write_text(
        json.dumps(rendered_hooks, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    target_path = actual_repo_path / target_relative
    manifest_lines.append(f"{actual_repo}\t{target_path}\t{rendered_path}")

for line in manifest_lines:
    print(line)
PY

MANIFEST=()
while IFS= read -r line; do
  if [[ -n "$line" ]]; then
    MANIFEST+=("$line")
  fi
done <"$MANIFEST_FILE"

if (( ${#REPO_FILTERS[@]} > 0 && ${#MANIFEST[@]} == 0 )); then
  die "No managed repos matched the requested --repo filters"
fi
if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed Copilot hook files were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed repo-local Copilot hook files from ${HOOKS_REGISTRY_FILE}."

DRIFT=0
for entry in ${MANIFEST[@]+"${MANIFEST[@]}"}; do
  IFS=$'\t' read -r repo target rendered <<<"$entry"

  log ""
  log "=== Repo Copilot Hooks (${repo}) ==="
  log "Target: $target"
  show_diff "$target" "$rendered"

  if is_drifted "$target" "$rendered"; then
    DRIFT=1
  fi

  if (( APPLY == 1 )); then
    ensure_parent_dir "$target"
    install_rendered_file "$rendered" "$target"
  fi
done

if (( CHECK == 1 )); then
  if (( DRIFT == 1 )); then
    printf 'ERROR: repo-local Copilot hook files are out of sync. Re-run sync-copilot-hooks.sh --apply for the affected repo(s).\n' >&2
    exit 1
  fi
  log "OK: repo-local Copilot hook files are in sync."
fi
