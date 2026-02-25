#!/usr/bin/env bash
set -euo pipefail

REGISTRY_FILE="${1:-${HOME}/.agents/skills/registry.md}"
APPLY=0

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--apply] [registry-file]

Sync skill symlinks from skills/registry.md managed table.

Defaults:
  registry-file: ~/.agents/skills/registry.md
  mode: dry-run

Options:
  --apply    Apply changes
  -h, --help Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      REGISTRY_FILE="$1"
      shift
      ;;
  esac
done

if [[ ! -f "$REGISTRY_FILE" ]]; then
  echo "Registry not found: $REGISTRY_FILE" >&2
  exit 1
fi

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

relpath_py() {
  python3 - "$1" "$2" <<'PY'
import os, sys
print(os.path.relpath(sys.argv[2], sys.argv[1]))
PY
}

sync_link() {
  local dst="$1"
  local src="$2"
  local dst_dir rel
  dst_dir="$(dirname "$dst")"
  rel="$(relpath_py "$dst_dir" "$src")"

  if [[ -L "$dst" ]]; then
    local cur
    cur="$(readlink "$dst")"
    if [[ "$cur" == "$rel" ]]; then
      echo "UNCHANGED $dst"
      return
    fi
  fi

  echo "SYNC $dst -> $rel"
  if [[ $APPLY -eq 1 ]]; then
    mkdir -p "$dst_dir"
    rm -rf "$dst"
    ln -s "$rel" "$dst"
  fi
}

rows="$(awk '
/managed-skills-table:start/ {in_tbl=1; next}
/managed-skills-table:end/ {in_tbl=0}
in_tbl && /^\|/ {
  line=$0
  gsub(/^[[:space:]]*\|/, "", line)
  gsub(/\|[[:space:]]*$/, "", line)
  n=split(line, a, "|")
  for (i=1; i<=n; i++) {
    gsub(/^[[:space:]]+/, "", a[i])
    gsub(/[[:space:]]+$/, "", a[i])
  }
  if (a[1] == "skill") next
  if (a[1] ~ /^-+$/) next
  print a[1]"|"a[2]"|"a[3]"|"a[4]"|"a[5]
}
' "$REGISTRY_FILE")"

if [[ -z "$rows" ]]; then
  echo "No managed rows found in registry table." >&2
  exit 1
fi

errors=0
while IFS='|' read -r skill origin scope repos source_path; do
  skill="$(trim "$skill")"
  origin="$(trim "$origin")"
  scope="$(trim "$scope")"
  repos="$(trim "$repos")"
  source_path="$(trim "$source_path")"

  [[ -n "$skill" ]] || continue

  case "$origin" in
    external|owned) ;;
    *)
      echo "ERROR invalid origin for $skill: $origin" >&2
      errors=$((errors + 1))
      continue
      ;;
  esac

  if [[ ! -f "$source_path/SKILL.md" ]]; then
    echo "ERROR source missing SKILL.md: $source_path ($skill)" >&2
    errors=$((errors + 1))
    continue
  fi

  case "$scope" in
    global)
      sync_link "${HOME}/.agents/skills/${skill}" "$source_path"
      ;;
    repo)
      IFS=',' read -r -a repo_arr <<< "$repos"
      if [[ ${#repo_arr[@]} -eq 0 ]]; then
        echo "ERROR no repos listed for $skill" >&2
        errors=$((errors + 1))
        continue
      fi
      for repo in "${repo_arr[@]}"; do
        repo="$(trim "$repo")"
        [[ -n "$repo" ]] || continue
        sync_link "${HOME}/GitHub/${repo}/.agents/skills/${skill}" "$source_path"
      done
      ;;
    *)
      echo "ERROR invalid scope for $skill: $scope" >&2
      errors=$((errors + 1))
      ;;
  esac
done <<< "$rows"

if [[ $errors -gt 0 ]]; then
  echo "Completed with errors: $errors" >&2
  exit 1
fi

if [[ $APPLY -eq 0 ]]; then
  echo "Dry run complete. Re-run with --apply to execute."
else
  echo "Apply complete."
fi
