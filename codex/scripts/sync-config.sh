#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APPLY=0
SYNC_GLOBAL=1
SYNC_XCODE=1
GITHUB_ROOT="${HOME}/GitHub"
GLOBAL_CONFIG="${HOME}/.codex/config.toml"
GLOBAL_AGENTS_DIR="${HOME}/.codex/agents"
XCODE_CONFIG="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/config.toml"
XCODE_AGENTS_DIR="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/agents"
XCODE_RULES="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/rules/xcode.rules"
CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
CANONICAL_GLOBAL_TEMPLATE="${CANONICAL_DIR}/global.config.toml"
CANONICAL_AGENTS_DIR="${CANONICAL_DIR}/agents"
CANONICAL_XCODE_TEMPLATE="${CANONICAL_DIR}/xcode.config.toml"
CANONICAL_XCODE_RULES_TEMPLATE="${CANONICAL_DIR}/xcode.rules"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="${HOME}/.local/state/codex-control-plane/runtime-config-backups"
BACKUP_MAX_AGE_DAYS=7
NOTIFY_SCRIPT_PATH="${HOME}/.agents/codex/scripts/notify.py"
SYSTEM_SKILLS_DISABLE_PATHS=(
  "${HOME}/.codex/skills/.system/openai-docs/SKILL.md"
  "${HOME}/.codex/skills/.system/skill-creator/SKILL.md"
  "${HOME}/.codex/skills/.system/skill-installer/SKILL.md"
)

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Sync canonical Codex settings from the `~/.agents` control plane into
terminal + Xcode Codex without overwriting machine/session-specific fields.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                    Apply changes in place (default: dry-run)
  --dry-run                  Show planned changes only (default)
  --global-only              Sync ~/.codex/config.toml only
  --xcode-only               Sync Xcode Codex config/rules only
  --github-root <path>       Root path for workspace-write writable_roots
                             (default: ~/GitHub)
  --global-config <path>     Override global codex config target
  --xcode-config <path>      Override Xcode codex config target
  --xcode-rules <path>       Override Xcode rules target
  --backup-root <path>       Store managed runtime backups outside ~/.codex
                             (default: ~/.local/state/codex-control-plane/runtime-config-backups)
  --canonical-dir <path>     Directory containing canonical templates:
                             global.config.toml, xcode.config.toml, xcode.rules
  -h, --help                 Show this help

Examples:
  ~/.agents/codex/scripts/sync-config.sh
  ~/.agents/codex/scripts/sync-config.sh --apply
  ~/.agents/codex/scripts/sync-config.sh --apply --xcode-only
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
    --github-root)
      GITHUB_ROOT="${2:-}"
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
    --xcode-rules)
      XCODE_RULES="${2:-}"
      shift 2
      ;;
    --backup-root)
      BACKUP_ROOT="${2:-}"
      shift 2
      ;;
    --canonical-dir)
      CANONICAL_DIR="${2:-}"
      CANONICAL_GLOBAL_TEMPLATE="${CANONICAL_DIR}/global.config.toml"
      CANONICAL_XCODE_TEMPLATE="${CANONICAL_DIR}/xcode.config.toml"
      CANONICAL_XCODE_RULES_TEMPLATE="${CANONICAL_DIR}/xcode.rules"
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

if [[ "$GITHUB_ROOT" != /* ]]; then
  die "--github-root must be an absolute path"
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

require_readable_file() {
  local file="$1"
  [[ -f "$file" ]] || die "Missing required file: $file"
  [[ -r "$file" ]] || die "File is not readable: $file"
}

ensure_no_conflict_markers() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  if rg -n '^(<<<<<<<|=======|>>>>>>>)' "$file" >/dev/null 2>&1; then
    die "Config contains unresolved merge conflict markers: $file"
  fi
}

prepare_work_file() {
  local source_file="$1"
  local work_file="$2"
  ensure_no_conflict_markers "$source_file"
  if [[ -f "$source_file" ]]; then
    cp "$source_file" "$work_file"
  else
    : > "$work_file"
  fi
}

extract_toml_entries() {
  local template_file="$1"
  awk '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
      section = $0
      sub(/^[[:space:]]*\[/, "", section)
      sub(/\][[:space:]]*$/, "", section)
      next
    }
    {
      line = $0
      sub(/^[[:space:]]*/, "", line)
      if (line ~ /^[A-Za-z0-9_]+[[:space:]]*=/) {
        key = line
        sub(/[[:space:]]*=.*/, "", key)
        value = line
        sub(/^[A-Za-z0-9_]+[[:space:]]*=[[:space:]]*/, "", value)
        sub(/[[:space:]]+$/, "", value)
        printf "%s\x1F%s\x1F%s\n", section, key, value
      }
    }
  ' "$template_file"
}

upsert_top_level_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file="$file.tmp"

  awk -v key="$key" -v value="$value" '
    BEGIN {
      in_sections = 0
      found = 0
      regex = "^[[:space:]]*" key "[[:space:]]*="
    }
    /^[[:space:]]*\[/ {
      if (!in_sections) {
        if (!found) {
          print key " = " value
          found = 1
        }
        in_sections = 1
      }
      print
      next
    }
    {
      if (!in_sections && $0 ~ regex) {
        if (!found) {
          print key " = " value
          found = 1
        }
        next
      }
      print
    }
    END {
      if (!found) {
        print key " = " value
      }
    }
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
}

remove_top_level_key() {
  local file="$1"
  local key="$2"
  local tmp_file="$file.tmp"

  awk -v key="$key" '
    BEGIN {
      in_sections = 0
      regex = "^[[:space:]]*" key "[[:space:]]*="
    }
    /^[[:space:]]*\[/ {
      in_sections = 1
      print
      next
    }
    {
      if (!in_sections && $0 ~ regex) {
        next
      }
      print
    }
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
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

render_global_config() {
  local target_file="$1"
  local template_file="$2"
  local section key value
  local notify_value

  while IFS=$'\x1f' read -r section key value; do
    [[ -n "$key" ]] || continue
    if [[ -z "$section" ]]; then
      upsert_top_level_key "$target_file" "$key" "$value"
    else
      upsert_section_key "$target_file" "$section" "$key" "$value"
    fi
  done < <(extract_toml_entries "$template_file")

  notify_value="[\"python3\", $(quote_toml_string "$NOTIFY_SCRIPT_PATH")]"
  upsert_top_level_key "$target_file" "notify" "$notify_value"

  # service_tier should follow the canonical template; if it is removed there,
  # prune stale copies from older live configs.
  if ! rg -n '^[[:space:]]*service_tier[[:space:]]*=' "$template_file" >/dev/null 2>&1; then
    remove_top_level_key "$target_file" "service_tier"
  fi

  prune_stale_agent_sections "$target_file" "$template_file"
}

sanitize_machine_specific_entries() {
  local target_file="$1"
  python3 - "$target_file" "$HOME" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


target = Path(sys.argv[1])
current_home = sys.argv[2].rstrip("/")

text = target.read_text(encoding="utf-8") if target.exists() else ""
lines = text.splitlines(keepends=True)

project_re = re.compile(r'^\[projects\."([^"]+)"\]\s*$')
path_re = re.compile(r'^\s*path\s*=\s*"([^"]*)"\s*$')
system_skill_re = re.compile(
    r"^/Users/[^/]+/\.codex/skills/\.system/skill-(creator|installer)/SKILL\.md$"
)


def keep_project_block(header: str) -> bool:
    m = project_re.match(header.strip())
    if not m:
        return True
    path = m.group(1)
    return not path.startswith("/Users/") or path == current_home or path.startswith(current_home + "/")


def keep_skill_block(block: list[str]) -> bool:
    for line in block:
        m = path_re.match(line.rstrip("\n"))
        if not m:
            continue
        path = m.group(1)
        if system_skill_re.match(path):
            return path.startswith(f"{current_home}/.codex/")
    return True


output: list[str] = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    if stripped == "[[skills.config]]":
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if s == "[[skills.config]]" or (s.startswith("[") and s.endswith("]")):
                break
            j += 1
        block = lines[i:j]
        if keep_skill_block(block):
            output.extend(block)
        i = j
        continue

    if stripped.startswith("[") and stripped.endswith("]"):
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if s == "[[skills.config]]" or (s.startswith("[") and s.endswith("]")):
                break
            j += 1
        block = lines[i:j]
        if keep_project_block(line):
            output.extend(block)
        i = j
        continue

    output.append(line)
    i += 1

target.write_text("".join(output), encoding="utf-8")
PY
}

ensure_system_skills_disabled() {
  local target_file="$1"
  python3 - "$target_file" "${SYSTEM_SKILLS_DISABLE_PATHS[@]}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


target = Path(sys.argv[1])
skill_paths = [p for p in sys.argv[2:] if p]

text = target.read_text(encoding="utf-8") if target.exists() else ""
lines = text.splitlines(keepends=True)


def find_block_ranges(data: list[str]) -> list[tuple[int, int]]:
    starts: list[int] = []
    for i, line in enumerate(data):
        if line.strip() == "[[skills.config]]":
            starts.append(i)
    ranges: list[tuple[int, int]] = []
    for idx, start in enumerate(starts):
        end = len(data)
        for j in range(start + 1, len(data)):
            s = data[j].strip()
            if s.startswith("[[") or (s.startswith("[") and s.endswith("]")):
                end = j
                break
        ranges.append((start, end))
    return ranges


path_re = re.compile(r'^\s*path\s*=\s*"([^"]*)"\s*$')
enabled_re = re.compile(r"^\s*enabled\s*=")

for skill_path in skill_paths:
    ranges = find_block_ranges(lines)
    matched_range = None
    for start, end in ranges:
        block_path = None
        for i in range(start, end):
            m = path_re.match(lines[i].rstrip("\n"))
            if m:
                block_path = m.group(1)
                break
        if block_path == skill_path:
            matched_range = (start, end)
            break

    if matched_range is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.extend(
            [
                "[[skills.config]]\n",
                f'path = "{skill_path}"\n',
                "enabled = false\n",
                "\n",
            ]
        )
        continue

    start, end = matched_range
    enabled_idx = None
    for i in range(start, end):
        if enabled_re.match(lines[i]):
            enabled_idx = i
            break

    if enabled_idx is None:
        insert_at = end
        if insert_at > start and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        lines.insert(insert_at, "enabled = false\n")
    else:
        lines[enabled_idx] = "enabled = false\n"


output = "".join(lines)
target.write_text(output, encoding="utf-8")
PY
}

prune_stale_agent_sections() {
  local target_file="$1"
  local template_file="$2"
  python3 - "$target_file" "$template_file" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


target = Path(sys.argv[1])
template = Path(sys.argv[2])

target_text = target.read_text(encoding="utf-8") if target.exists() else ""
template_text = template.read_text(encoding="utf-8") if template.exists() else ""

agent_header_re = re.compile(r'^\[agents\.([^\]]+)\]\s*$')

allowed_agents: set[str] = set()
for line in template_text.splitlines():
    m = agent_header_re.match(line.strip())
    if m:
        allowed_agents.add(m.group(1))

lines = target_text.splitlines(keepends=True)
output: list[str] = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if s == "[[skills.config]]" or (s.startswith("[") and s.endswith("]")):
                break
            j += 1
        block = lines[i:j]
        m = agent_header_re.match(stripped)
        if m and m.group(1) not in allowed_agents:
            i = j
            continue
        output.extend(block)
        i = j
        continue

    output.append(line)
    i += 1

target.write_text("".join(output), encoding="utf-8")
PY
}

render_xcode_config() {
  local target_file="$1"
  local template_file="$2"
  local writable_roots
  local project_section
  local section key value
  writable_roots="[$(quote_toml_string "$GITHUB_ROOT")]"
  project_section="projects.$(quote_toml_string "$GITHUB_ROOT")"

  while IFS=$'\x1f' read -r section key value; do
    [[ -n "$key" ]] || continue
    if [[ -z "$section" ]]; then
      upsert_top_level_key "$target_file" "$key" "$value"
    elif [[ "$section" == "features" || "$section" == "sandbox_workspace_write" || "$section" == "mcp_servers.openaiDeveloperDocs" ]]; then
      upsert_section_key "$target_file" "$section" "$key" "$value"
    fi
  done < <(extract_toml_entries "$template_file")

  # Keep writable roots machine-specific via CLI/home path, regardless of template value.
  upsert_section_key "$target_file" "sandbox_workspace_write" "writable_roots" "$writable_roots"
  # Ensure Xcode Codex trusts all repos under the configured GitHub root.
  upsert_section_key "$target_file" "$project_section" "trust_level" "\"trusted\""

  if ! rg -n '^[[:space:]]*service_tier[[:space:]]*=' "$template_file" >/dev/null 2>&1; then
    remove_top_level_key "$target_file" "service_tier"
  fi

  prune_stale_agent_sections "$target_file" "$template_file"
}

render_xcode_rules() {
  local rendered_rules_file="$1"
  local template_rules_file="$2"
  cp "$template_rules_file" "$rendered_rules_file"
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

prune_old_backups() {
  [[ -d "$BACKUP_ROOT" ]] || return 0
  find "$BACKUP_ROOT" -type f -name '*.bak.*' -mtime "+${BACKUP_MAX_AGE_DAYS}" -delete 2>/dev/null || true
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

sync_global() {
  local original="$GLOBAL_CONFIG"
  local rendered="${TMP_DIR}/global.config.toml"

  require_readable_file "$CANONICAL_GLOBAL_TEMPLATE"
  ensure_parent_dir "$original"
  prepare_work_file "$original" "$rendered"
  sanitize_machine_specific_entries "$rendered"
  render_global_config "$rendered" "$CANONICAL_GLOBAL_TEMPLATE"
  ensure_system_skills_disabled "$rendered"

  log ""
  log "=== Global Codex Config (${original}) ==="
  show_diff "$original" "$rendered"

  if (( APPLY == 1 )); then
    install_rendered_file "$rendered" "$original"
  fi

  sync_agent_role_configs "Global Agent Roles" "$CANONICAL_AGENTS_DIR" "$GLOBAL_AGENTS_DIR"
}

sync_xcode() {
  local original_cfg="$XCODE_CONFIG"
  local rendered_cfg="${TMP_DIR}/xcode.config.toml"
  local original_rules="$XCODE_RULES"
  local rendered_rules="${TMP_DIR}/xcode.rules"

  require_readable_file "$CANONICAL_XCODE_TEMPLATE"
  require_readable_file "$CANONICAL_XCODE_RULES_TEMPLATE"
  ensure_parent_dir "$original_cfg"
  ensure_parent_dir "$original_rules"

  prepare_work_file "$original_cfg" "$rendered_cfg"
  sanitize_machine_specific_entries "$rendered_cfg"
  render_xcode_config "$rendered_cfg" "$CANONICAL_XCODE_TEMPLATE"
  render_xcode_rules "$rendered_rules" "$CANONICAL_XCODE_RULES_TEMPLATE"

  log ""
  log "=== Xcode Codex Config (${original_cfg}) ==="
  show_diff "$original_cfg" "$rendered_cfg"
  log ""
  log "=== Xcode Codex Rules (${original_rules}) ==="
  show_diff "$original_rules" "$rendered_rules"

  if (( APPLY == 1 )); then
    install_rendered_file "$rendered_cfg" "$original_cfg"
    install_rendered_file "$rendered_rules" "$original_rules"
  fi

  sync_agent_role_configs "Xcode Agent Roles" "$CANONICAL_AGENTS_DIR" "$XCODE_AGENTS_DIR"
}

sync_agent_role_configs() {
  local label="$1"
  local source_dir="$2"
  local target_dir="$3"
  local source_file target_file rendered_file basename target_existing
  local -a source_basenames=()

  if [[ ! -d "$source_dir" ]]; then
    return
  fi

  shopt -s nullglob
  for source_file in "$source_dir"/*.toml; do
    basename="$(basename "$source_file")"
    source_basenames+=("$basename")
    target_file="${target_dir}/${basename}"
    rendered_file="${TMP_DIR}/${label// /_}-${basename}"

    require_readable_file "$source_file"
    ensure_parent_dir "$target_file"
    cp "$source_file" "$rendered_file"

    log ""
    log "=== ${label} (${target_file}) ==="
    show_diff "$target_file" "$rendered_file"

    if (( APPLY == 1 )); then
      install_rendered_file "$rendered_file" "$target_file"
    fi
  done

  if [[ -d "$target_dir" ]]; then
    for target_existing in "$target_dir"/*.toml; do
      basename="$(basename "$target_existing")"
      if [[ " ${source_basenames[*]} " == *" ${basename} "* ]]; then
        continue
      fi

      log ""
      log "=== ${label} (${target_existing}) ==="
      log "Stale managed agent role file will be removed."
      if (( APPLY == 1 )); then
        rm -f "$target_existing"
        log "Removed: $target_existing"
      fi
    done
  fi
  shopt -u nullglob
}

log "Control Plane: $CONTROL_PLANE_DIR"
log "Canonical Dir: $CANONICAL_DIR"
if (( APPLY == 1 )); then
  log "Mode: APPLY"
  prune_old_backups
else
  log "Mode: DRY-RUN (no files written)"
fi

if (( SYNC_GLOBAL == 1 )); then
  sync_global
fi
if (( SYNC_XCODE == 1 )); then
  sync_xcode
fi

log ""
if (( APPLY == 1 )); then
  log "Done. Restart Codex/Xcode to ensure new settings are loaded."
else
  log "Dry-run complete. Re-run with --apply to write changes."
fi
