#!/usr/bin/env bash
set -euo pipefail

APPLY=0
SYNC_GLOBAL=1
SYNC_XCODE=1
ROOTS=()
GLOBAL_CONFIG="${HOME}/.codex/config.toml"
XCODE_CONFIG="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/config.toml"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="${HOME}/.local/state/codex-control-plane/runtime-config-backups"
BACKUP_MAX_AGE_DAYS=7
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REGISTRY_FILE="${CONTROL_PLANE_DIR}/config/repo-bootstrap.json"
ROOTS_EXPLICIT=0

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Discover Git repos under one or more roots and mark each repo root as trusted in
Codex config. Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diff only (default)
  --global-only          Update ~/.codex/config.toml only
  --xcode-only           Update Xcode Codex config only
  --root <path>          Root to scan for repos (repeatable; bypass registry repo list)
  --registry <path>      Override repo bootstrap registry used for managed repos
  --global-config <p>    Override global config target
  --xcode-config <p>     Override Xcode config target
  --backup-root <path>   Store managed runtime backups outside ~/.codex
                         (default: ~/.local/state/codex-control-plane/runtime-config-backups)
  -h, --help             Show this help

Examples:
  ~/.agents/codex/scripts/sync-trusted-projects.sh
  ~/.agents/codex/scripts/sync-trusted-projects.sh --apply
  ~/.agents/codex/scripts/sync-trusted-projects.sh --apply --root ~/GitHub --root ~/Work
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
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --global-only)
      SYNC_GLOBAL=1
      SYNC_XCODE=0
      shift
      ;;
    --xcode-only)
      SYNC_GLOBAL=0
      SYNC_XCODE=1
      shift
      ;;
    --root)
      ROOTS_EXPLICIT=1
      ROOTS+=("${2:-}")
      shift 2
      ;;
    --registry)
      REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --global-config)
      GLOBAL_CONFIG="${2:-}"
      shift 2
      ;;
    --xcode-config)
      XCODE_CONFIG="${2:-}"
      shift 2
      ;;
    --backup-root)
      BACKUP_ROOT="${2:-}"
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

if (( SYNC_GLOBAL == 0 && SYNC_XCODE == 0 )); then
  die "Nothing selected. Use default/all, --global-only, or --xcode-only."
fi

if (( APPLY == 1 )); then
  [[ -d "$BACKUP_ROOT" ]] || mkdir -p "$BACKUP_ROOT"
  find "$BACKUP_ROOT" -type f -name '*.bak.*' -mtime "+${BACKUP_MAX_AGE_DAYS}" -delete 2>/dev/null || true
fi

quote_toml_string() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

ensure_parent_dir() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
}

prepare_work_file() {
  local source_file="$1"
  local work_file="$2"
  if [[ -f "$source_file" ]]; then
    cp "$source_file" "$work_file"
  else
    : > "$work_file"
  fi
}

upsert_section_key() {
  local file="$1"
  local section="$2"
  local key="$3"
  local value="$4"
  local tmp_file="$file.tmp"

  awk -v section="$section" -v key="$key" -v value="$value" '
    BEGIN {
      in_target = 0
      section_found = 0
      key_written = 0
      key_regex = "^[[:space:]]*" key "[[:space:]]*="
      section_regex = "^[[:space:]]*\\[" section "\\][[:space:]]*$"
      any_section_regex = "^[[:space:]]*\\["
    }
    {
      if ($0 ~ any_section_regex) {
        if (in_target && !key_written) {
          print key " = " value
          key_written = 1
        }
        if ($0 ~ section_regex) {
          in_target = 1
          section_found = 1
        } else {
          in_target = 0
        }
        print
        next
      }
      if (in_target && $0 ~ key_regex) {
        if (!key_written) {
          print key " = " value
          key_written = 1
        }
        next
      }
      print
    }
    END {
      if (!section_found) {
        print ""
        print "[" section "]"
        print key " = " value
      } else if (in_target && !key_written) {
        print key " = " value
      }
    }
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
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
  local backup=""
  local mode="600"

  if [[ -f "$target" ]] && cmp -s "$target" "$rendered"; then
    log "No change: $target"
    return 0
  fi

  if [[ -f "$target" ]]; then
    mode="$(stat -f "%Lp" "$target" 2>/dev/null || echo 600)"
    backup="${BACKUP_ROOT}/${target#/}.bak.${TIMESTAMP}"
    mkdir -p "$(dirname "$backup")"
    cp "$target" "$backup"
    log "Backup: $backup"
  fi

  install -m "$mode" "$rendered" "$target"
  log "Updated: $target"
}

discover_repo_roots() {
  local root="$1"
  [[ -d "$root" ]] || return 0

  python3 - "$root" <<'PY'
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
seen: set[str] = set()

for dirpath, dirnames, filenames in os.walk(root, topdown=True):
    has_git = ".git" in dirnames or ".git" in filenames
    if ".git" in dirnames:
        dirnames.remove(".git")
    if not has_git:
        continue
    try:
        repo_root = subprocess.run(
            ["git", "-C", dirpath, "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        continue
    if repo_root and repo_root not in seen:
        seen.add(repo_root)
        print(repo_root)
PY
}

collect_all_repo_roots() {
  local root repo
  declare -A seen=()

  for root in "${ROOTS[@]}"; do
    if [[ -z "$root" ]]; then
      continue
    fi
    case "$root" in
      "~")
        root="$HOME"
        ;;
      "~/"*)
        root="${HOME}/${root#~/}"
        ;;
      /*)
        ;;
      *)
        root="$(cd "$root" 2>/dev/null && pwd -P)" || continue
        ;;
    esac
    while IFS= read -r repo; do
      [[ -n "$repo" ]] || continue
      seen["$repo"]=1
    done < <(discover_repo_roots "$root")
  done

  for repo in "${!seen[@]}"; do
    printf '%s\n' "$repo"
  done | sort
}

collect_registry_repos() {
  [[ -f "$REGISTRY_FILE" ]] || return 0

  python3 - "$REGISTRY_FILE" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

registry = Path(sys.argv[1]).expanduser().resolve()
data = json.loads(registry.read_text(encoding="utf-8"))
repos = data.get("repos", [])
if not isinstance(repos, list):
    raise TypeError("repos must be an array")

for item in repos:
    if not isinstance(item, dict):
        raise TypeError("each repo entry must be an object")
    raw = item.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise TypeError("repo.path must be a non-empty string")
    path = Path(raw).expanduser().resolve()
    try:
        repo_root = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        if path.exists():
            print(f"WARNING: skipping non-git repo path: {path}", file=sys.stderr)
        continue
    if repo_root:
        print(str(Path(repo_root).resolve()))
PY
}

apply_trust_entries() {
  local target_file="$1"
  shift
  local repo project_section

  for repo in "$@"; do
    project_section="projects.$(quote_toml_string "$repo")"
    upsert_section_key "$target_file" "$project_section" "trust_level" "\"trusted\""
  done
}

sync_target() {
  local label="$1"
  local original="$2"
  shift 2
  local rendered="${TMP_DIR}/$(basename "$original").${label}.tmp"

  ensure_parent_dir "$original"
  prepare_work_file "$original" "$rendered"
  apply_trust_entries "$rendered" "$@"

  log ""
  log "=== Trusted Projects (${label}: ${original}) ==="
  show_diff "$original" "$rendered"

  if (( APPLY == 1 )); then
    install_rendered_file "$rendered" "$original"
  fi
}

if (( ROOTS_EXPLICIT == 0 )); then
  mapfile -t REPO_ROOTS < <(collect_registry_repos)
fi

if (( ROOTS_EXPLICIT == 1 )); then
  mapfile -t REPO_ROOTS < <(collect_all_repo_roots)
fi

if (( ${#REPO_ROOTS[@]} == 0 )); then
  ROOTS=("${HOME}/GitHub")
  mapfile -t REPO_ROOTS < <(collect_all_repo_roots)
fi

if (( ${#REPO_ROOTS[@]} == 0 )); then
  die "No Git repos discovered under the configured root set."
fi

log "Discovered ${#REPO_ROOTS[@]} trusted repo roots."
for repo in "${REPO_ROOTS[@]}"; do
  log "  - $repo"
done

if (( SYNC_GLOBAL == 1 )); then
  sync_target "global" "$GLOBAL_CONFIG" "${REPO_ROOTS[@]}"
fi

if (( SYNC_XCODE == 1 )); then
  sync_target "xcode" "$XCODE_CONFIG" "${REPO_ROOTS[@]}"
fi
