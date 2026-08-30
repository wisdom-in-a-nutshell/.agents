#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"

APPLY=0
SYNC_GLOBAL=1
GITHUB_ROOT="${HOME}/GitHub"
GLOBAL_CONFIG="${HOME}/.codex/config.toml"
GLOBAL_HOOKS="${HOME}/.codex/hooks.json"
GLOBAL_AGENTS_DIR="${HOME}/.codex/agents"
GLOBAL_AUTH="${HOME}/.codex/auth.json"
GLOBAL_MCP_CREDENTIALS="${HOME}/.codex/.credentials.json"
CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
MCP_REGISTRY="${ROOT_DIR}/mcp/config/presets.json"
PLUGIN_REGISTRY="${ROOT_DIR}/plugins/registry.json"
HOOKS_REGISTRY="${ROOT_DIR}/hooks/registry.json"
CANONICAL_GLOBAL_TEMPLATE="${CANONICAL_DIR}/global.config.toml"
BUNDLED_SKILLS_POLICY="${CANONICAL_DIR}/bundled-skills-policy.json"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Sync canonical Codex settings from the `~/GitHub/agents` control plane into
the terminal Codex runtime without overwriting machine-specific fields.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                    Apply changes in place (default: dry-run)
  --dry-run                  Show planned changes only (default)
  --global-only              Sync ~/.codex/config.toml only
  --github-root <path>       Root path for workspace-write writable_roots
                             (default: ~/GitHub)
  --global-config <path>     Override global codex config target
  --global-hooks <path>      Override global codex hooks target
  --global-auth <path>       Override global Codex auth source
  --global-mcp-credentials <path>
                             Override global Codex MCP OAuth credentials source
  --canonical-dir <path>     Directory containing canonical templates:
                             global.config.toml, *.config.toml profile files,
                             and bundled-skills-policy.json
  --mcp-registry <path>      Shared MCP registry
                             (default: mcp/config/presets.json)
  --plugin-registry <path>   Native Codex plugin registry
                             (default: plugins/registry.json)
  --hooks-registry <path>    Shared hooks registry
                             (default: hooks/registry.json)
  -h, --help                 Show this help

Examples:
  ~/GitHub/agents/codex/scripts/sync-config.sh
  ~/GitHub/agents/codex/scripts/sync-config.sh --apply
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
    --global-hooks)
      GLOBAL_HOOKS="${2:-}"
      shift 2
      ;;
    --global-auth)
      GLOBAL_AUTH="${2:-}"
      shift 2
      ;;
    --global-mcp-credentials)
      GLOBAL_MCP_CREDENTIALS="${2:-}"
      shift 2
      ;;
    --canonical-dir)
      CANONICAL_DIR="${2:-}"
      CANONICAL_GLOBAL_TEMPLATE="${CANONICAL_DIR}/global.config.toml"
      BUNDLED_SKILLS_POLICY="${CANONICAL_DIR}/bundled-skills-policy.json"
      shift 2
      ;;
    --mcp-registry)
      MCP_REGISTRY="${2:-}"
      shift 2
      ;;
    --plugin-registry)
      PLUGIN_REGISTRY="${2:-}"
      shift 2
      ;;
    --hooks-registry)
      HOOKS_REGISTRY="${2:-}"
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

if (( SYNC_GLOBAL == 0 )); then
  die "Nothing selected. Use default/all or --global-only."
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

load_codex_skill_disable_paths() {
  local policy_file="$1"
  python3 - "$policy_file" "$HOME" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


policy_path = Path(sys.argv[1]).expanduser().resolve()
home = sys.argv[2].rstrip("/")

try:
    data = json.loads(policy_path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit(f"ERROR: invalid JSON in bundled skills policy {policy_path}: {exc}")

roots = data.get("roots")
if not isinstance(roots, dict):
    raise SystemExit(f"ERROR: bundled skills policy roots must be an object: {policy_path}")

seen_paths: set[str] = set()
for root_name, root_config in roots.items():
    if not isinstance(root_config, dict):
        raise SystemExit(f"ERROR: bundled skills policy roots.{root_name} must be an object")
    root_path = root_config.get("path")
    disabled = root_config.get("disabled", [])
    if not isinstance(root_path, str) or not root_path.strip():
        raise SystemExit(f"ERROR: bundled skills policy roots.{root_name}.path must be a non-empty string")
    if not isinstance(disabled, list):
        raise SystemExit(f"ERROR: bundled skills policy roots.{root_name}.disabled must be an array")
    expanded_root = root_path.replace("~", home, 1) if root_path == "~" or root_path.startswith("~/") else root_path
    for skill_name in disabled:
        if not isinstance(skill_name, str) or not skill_name.strip() or "/" in skill_name:
            raise SystemExit(
                f"ERROR: bundled skills policy roots.{root_name}.disabled contains invalid skill name: {skill_name!r}"
            )
        skill_path = str(Path(expanded_root) / skill_name / "SKILL.md")
        if skill_path in seen_paths:
            continue
        seen_paths.add(skill_path)
        print(skill_path)
PY
}

extract_global_mcp_entries() {
  local registry_file="$1"
  python3 - "$registry_file" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        items = []
        for key in sorted(value):
            if not isinstance(key, str):
                raise TypeError(f"Unsupported TOML key type: {key!r}")
            escaped_key = key.replace("\\", "\\\\").replace('"', '\\"')
            items.append(f'"{escaped_key}" = {toml_value(value[key])}')
        return "{ " + ", ".join(items) + " }"
    raise TypeError(f"Unsupported TOML value: {value!r}")


registry_path = Path(sys.argv[1]).expanduser().resolve()
data = json.loads(registry_path.read_text(encoding="utf-8"))
if not isinstance(data, dict):
    raise SystemExit(f"{registry_path}: MCP registry root must be an object")

presets = data.get("presets", {})
if not isinstance(presets, dict):
    raise SystemExit(f"{registry_path}: presets must be an object")
if data.get("version") != 2:
    raise SystemExit(f"{registry_path}: version must be 2")
for name, preset in presets.items():
    if not isinstance(preset, dict):
        raise SystemExit(f"{registry_path}: preset `{name}` must be an object")
    transport = preset.get("transport")
    if transport not in {"http", "stdio"}:
        raise SystemExit(f"{registry_path}: preset `{name}` has invalid transport `{transport}`")
    if not isinstance(preset.get("targets"), list):
        raise SystemExit(f"{registry_path}: preset `{name}` targets must be an array")
PY
}

extract_codex_plugin_entries() {
  local registry_file="$1"
  PYTHONPATH="$ROOT_DIR" python3 - "$registry_file" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

from plugins.derived import validate_plugin_registry


registry_path = Path(sys.argv[1]).expanduser().resolve()
data = json.loads(registry_path.read_text(encoding="utf-8"))
plugins, _, _ = validate_plugin_registry(
    data,
    root_dir=registry_path.parent.parent,
    home=Path.home(),
)

for plugin in plugins:
    if plugin.scope != "global":
        continue
    enabled = "true" if plugin.enabled else "false"
    print(f'plugins."{plugin.plugin_id}"\x1Fenabled\x1F{enabled}')
PY
}

extract_openai_bundled_marketplace_entries() {
  local marketplace_path="${CODEX_BUNDLED_MARKETPLACE:-/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled}"
  printf 'marketplaces.openai-bundled\x1Fsource_type\x1F"local"\n'
  printf 'marketplaces.openai-bundled\x1Fsource\x1F%s\n' "$(quote_toml_string "$marketplace_path")"
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

remove_section_key() {
  local file="$1"
  local section="$2"
  local key="$3"
  local tmp_file="$file.tmp"

  awk -v section="$section" -v key="$key" '
    BEGIN {
      in_target = 0
      key_regex = "^[[:space:]]*" key "[[:space:]]*="
      section_regex = "^[[:space:]]*\\[" section "\\][[:space:]]*$"
      any_section_regex = "^[[:space:]]*\\["
    }
    {
      if ($0 ~ any_section_regex) {
        if ($0 ~ section_regex) {
          in_target = 1
        } else {
          in_target = 0
        }
        print
        next
      }
      if (in_target && $0 ~ key_regex) {
        next
      }
      print
    }
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
}

remove_legacy_embedded_profiles() {
  local file="$1"

  python3 - "$file" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
section_re = re.compile(r"^\s*\[([^]]+)]\s*(?:#.*)?$")
in_legacy_section = False
output: list[str] = []

for line in lines:
    match = section_re.match(line.rstrip("\n"))
    if match:
        section = match.group(1)
        in_legacy_section = section == "profiles" or section.startswith("profiles.")
    if not in_legacy_section:
        output.append(line)

path.write_text("".join(output), encoding="utf-8")
PY
}

render_global_config() {
  local target_file="$1"
  local template_file="$2"
  local mcp_registry_file="$3"
  local plugin_registry_file="$4"
  local section key value

  while IFS=$'\x1f' read -r section key value; do
    [[ -n "$key" ]] || continue
    if [[ -z "$section" ]]; then
      upsert_top_level_key "$target_file" "$key" "$value"
    else
      upsert_section_key "$target_file" "$section" "$key" "$value"
    fi
  done < <(extract_toml_entries "$template_file")

  while IFS=$'\x1f' read -r section key value; do
    [[ -n "$key" ]] || continue
    upsert_section_key "$target_file" "$section" "$key" "$value"
  done < <(extract_global_mcp_entries "$mcp_registry_file")

  while IFS=$'\x1f' read -r section key value; do
    [[ -n "$key" ]] || continue
    upsert_section_key "$target_file" "$section" "$key" "$value"
  done < <(extract_codex_plugin_entries "$plugin_registry_file")

  while IFS=$'\x1f' read -r section key value; do
    [[ -n "$key" ]] || continue
    upsert_section_key "$target_file" "$section" "$key" "$value"
  done < <(extract_openai_bundled_marketplace_entries)

  # Codex turn-end automation now lives in hooks/registry.json -> Stop.
  remove_top_level_key "$target_file" "notify"

  # Codex profiles are standalone ~/.codex/<name>.config.toml overlays. Remove
  # the retired embedded autofix selector/table so `--profile autofix` works.
  remove_top_level_key "$target_file" "profile"
  remove_legacy_embedded_profiles "$target_file"

  # Thread-selection defaults should follow the canonical template; if they are
  # removed there, prune stale copies from older live configs so client choices
  # can win when a new thread starts.
  if ! rg -n '^[[:space:]]*model[[:space:]]*=' "$template_file" >/dev/null 2>&1; then
    remove_top_level_key "$target_file" "model"
  fi
  if ! rg -n '^[[:space:]]*service_tier[[:space:]]*=' "$template_file" >/dev/null 2>&1; then
    remove_top_level_key "$target_file" "service_tier"
  fi
  if ! rg -n '^[[:space:]]*model_provider[[:space:]]*=' "$template_file" >/dev/null 2>&1; then
    remove_top_level_key "$target_file" "model_provider"
  fi
  if ! rg -n '^[[:space:]]*fast_mode[[:space:]]*=' "$template_file" >/dev/null 2>&1; then
    remove_section_key "$target_file" "features" "fast_mode"
  fi
  if ! rg -n '^[[:space:]]*default-service-tier[[:space:]]*=' "$template_file" >/dev/null 2>&1; then
    remove_section_key "$target_file" "desktop" "default-service-tier"
  fi
  # Codex 0.129 renamed the hooks feature flag; prune the older managed key
  # when applying the new canonical template.
  remove_section_key "$target_file" "features" "codex_hooks"

  prune_stale_agent_sections "$target_file" "$template_file"
  prune_stale_app_sections "$target_file" "$template_file"
  prune_stale_plugin_sections "$target_file" "$template_file" "$plugin_registry_file"
  prune_stale_model_provider_sections "$target_file" "$template_file"
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
managed_skill_re = re.compile(
    r"^/Users/[^/]+/\.codex/skills/(?:(?:\.system/(imagegen|openai-docs|plugin-creator|skill-creator|skill-installer))|(?:codex-primary-runtime/(slides|spreadsheets)))/SKILL\.md$"
)


def keep_project_block(header: str) -> bool:
    m = project_re.match(header.strip())
    if not m:
        return True
    path = m.group(1)
    if "/.tmp/" in path or "/tmp/" in path:
        return False
    return not path.startswith("/Users/") or path == current_home or path.startswith(current_home + "/")


def keep_skill_block(block: list[str]) -> bool:
    for line in block:
        m = path_re.match(line.rstrip("\n"))
        if not m:
            continue
        path = m.group(1)
        if managed_skill_re.match(path):
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

while output and not output[-1].strip():
    output.pop()

text = "".join(output)
if text and not text.endswith("\n"):
    text += "\n"
target.write_text(text, encoding="utf-8")
PY
}

ensure_system_skills_disabled() {
  local target_file="$1"
  local policy_file="$2"
  local paths_file="${TMP_DIR}/codex-skill-disable-paths.txt"
  local -a skill_paths=()

  load_codex_skill_disable_paths "$policy_file" > "$paths_file"
  while IFS= read -r skill_path; do
    [[ -n "$skill_path" ]] || continue
    skill_paths+=("$skill_path")
  done < "$paths_file"

  python3 - "$target_file" "${skill_paths[@]}" <<'PY'
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

while output and not output[-1].strip():
    output.pop()

text = "".join(output)
if text and not text.endswith("\n"):
    text += "\n"
target.write_text(text, encoding="utf-8")
PY
}

prune_stale_mcp_sections() {
  local target_file="$1"
  local registry_file="$2"
  python3 - "$target_file" "$registry_file" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


target = Path(sys.argv[1])
registry = Path(sys.argv[2])

target_text = target.read_text(encoding="utf-8") if target.exists() else ""
registry_data = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}

mcp_header_re = re.compile(r'^\[mcp_servers\.([^\]]+)\]\s*$')

allowed_servers: set[str] = set()

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
        m = mcp_header_re.match(stripped)
        if m and m.group(1) not in allowed_servers:
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

prune_stale_app_sections() {
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

app_header_re = re.compile(r'^\[apps\.([^\]]+)\]\s*$')

allowed_apps: set[str] = set()
for line in template_text.splitlines():
    m = app_header_re.match(line.strip())
    if m:
        allowed_apps.add(m.group(1))

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
        m = app_header_re.match(stripped)
        if m and m.group(1) not in allowed_apps:
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

prune_stale_plugin_sections() {
  local target_file="$1"
  local template_file="$2"
  local plugin_registry_file="$3"
  PYTHONPATH="$ROOT_DIR" python3 - "$target_file" "$template_file" "$plugin_registry_file" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from plugins.derived import validate_plugin_registry

target = Path(sys.argv[1])
template = Path(sys.argv[2])
plugin_registry = Path(sys.argv[3]).expanduser().resolve()

target_text = target.read_text(encoding="utf-8") if target.exists() else ""
template_text = template.read_text(encoding="utf-8") if template.exists() else ""

plugin_header_re = re.compile(r'^\[plugins\."([^"]+)"\]\s*$')
legacy_plugin_header_re = re.compile(r'^\[plugins\.([^\]"]+@[^\]"]+)\]\s*$')

allowed_plugins: set[str] = set()
for line in template_text.splitlines():
    m = plugin_header_re.match(line.strip())
    if m:
        allowed_plugins.add(m.group(1))

if plugin_registry.is_file():
    data = json.loads(plugin_registry.read_text(encoding="utf-8"))
    plugins, _, _ = validate_plugin_registry(
        data,
        root_dir=plugin_registry.parent.parent,
        home=Path.home(),
    )
    for plugin in plugins:
        if plugin.scope == "global":
            allowed_plugins.add(plugin.plugin_id)

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
        m = plugin_header_re.match(stripped)
        legacy = legacy_plugin_header_re.match(stripped)
        if legacy:
            i = j
            continue
        if m and m.group(1) not in allowed_plugins:
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

prune_stale_model_provider_sections() {
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

provider_header_re = re.compile(r'^\[model_providers\.([^\]]+)\]\s*$')

allowed_providers: set[str] = set()
for line in template_text.splitlines():
    m = provider_header_re.match(line.strip())
    if m:
        allowed_providers.add(m.group(1))

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
        m = provider_header_re.match(stripped)
        if m and m.group(1) not in allowed_providers:
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

render_codex_hooks() {
  local registry_file="$1"
  local rendered_hooks_file="$2"

  PYTHONPATH="$ROOT_DIR" python3 -m hooks.control_plane render-codex \
    --registry "$registry_file" \
    --output "$rendered_hooks_file"
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
  local mode="600"

  if [[ -f "$target" ]] && cmp -s "$target" "$rendered"; then
    log "No change: $target"
    return 0
  fi

  if [[ -f "$target" ]]; then
    mode="$(stat -f "%Lp" "$target" 2>/dev/null || echo 600)"
  fi

  install -m "$mode" "$rendered" "$target"
  log "Updated: $target"
}

resolved_path() {
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

sync_sensitive_symlink() {
  local label="$1"
  local source="$2"
  local target="$3"
  local source_resolved
  local target_resolved

  if [[ ! -e "$source" ]]; then
    if [[ -L "$source" ]]; then
      log "WARNING: skipping ${label}; source symlink is broken: $source"
    else
      log "SKIP ${label}; source missing: $source"
    fi
    return 0
  fi
  if [[ ! -f "$source" ]]; then
    die "${label} source is not a file: $source"
  fi

  source_resolved="$(resolved_path "$source")"
  if [[ -L "$target" ]]; then
    target_resolved="$(resolved_path "$target")"
    if [[ "$target_resolved" == "$source_resolved" ]]; then
      log "UNCHANGED ${target} -> ${source}"
      return 0
    fi
    log "WARNING: skipping ${label}; ${target} links to ${target_resolved}, expected ${source_resolved}"
    return 0
  fi
  if [[ -e "$target" ]]; then
    log "WARNING: skipping ${label}; existing non-symlink credential file: $target"
    return 0
  fi

  log "SYNC ${target} -> ${source}"
  if (( APPLY == 1 )); then
    ensure_parent_dir "$target"
    ln -s "$source" "$target"
  fi
}

cleanup_agent_role_dir() {
  local label="$1"
  local target_dir="$2"
  local target_existing

  if [[ ! -d "$target_dir" ]]; then
    return
  fi

  shopt -s nullglob
  for target_existing in "$target_dir"/*.toml; do
    log ""
    log "=== ${label} (${target_existing}) ==="
    log "Stale managed agent role file will be removed."
    show_diff "$target_existing" /dev/null
    if (( APPLY == 1 )); then
      rm -f "$target_existing"
      log "Removed: $target_existing"
    fi
  done
  shopt -u nullglob
}

sync_global() {
  local original="$GLOBAL_CONFIG"
  local rendered="${TMP_DIR}/global.config.toml"
  local hooks_original="$GLOBAL_HOOKS"
  local hooks_rendered="${TMP_DIR}/hooks.json"

  require_readable_file "$CANONICAL_GLOBAL_TEMPLATE"
  require_readable_file "$BUNDLED_SKILLS_POLICY"
  require_readable_file "$MCP_REGISTRY"
  require_readable_file "$PLUGIN_REGISTRY"
  require_readable_file "$HOOKS_REGISTRY"
  ensure_parent_dir "$original"
  ensure_parent_dir "$hooks_original"
  prepare_work_file "$original" "$rendered"
  sanitize_machine_specific_entries "$rendered"
  render_global_config "$rendered" "$CANONICAL_GLOBAL_TEMPLATE" "$MCP_REGISTRY" "$PLUGIN_REGISTRY"
  ensure_system_skills_disabled "$rendered" "$BUNDLED_SKILLS_POLICY"
  render_codex_hooks "$HOOKS_REGISTRY" "$hooks_rendered"

  log ""
  log "=== Global Codex Config (${original}) ==="
  show_diff "$original" "$rendered"
  log ""
  log "=== Global Codex Hooks (${hooks_original}) ==="
  show_diff "$hooks_original" "$hooks_rendered"

  if (( APPLY == 1 )); then
    install_rendered_file "$rendered" "$original"
    install_rendered_file "$hooks_rendered" "$hooks_original"
  fi

  cleanup_agent_role_dir "Global Agent Roles" "$GLOBAL_AGENTS_DIR"
}

sync_profile_configs() {
  local target_dir
  local profile_template
  local target_file
  local profile_name

  target_dir="$(dirname "$GLOBAL_CONFIG")"
  ensure_parent_dir "${target_dir}/config.toml"

  shopt -s nullglob
  for profile_template in "$CANONICAL_DIR"/*.config.toml; do
    profile_name="$(basename "$profile_template")"
    [[ "$profile_name" == "global.config.toml" ]] && continue
    require_readable_file "$profile_template"
    ensure_no_conflict_markers "$profile_template"
    target_file="${target_dir}/${profile_name}"

    log ""
    log "=== Codex Profile (${target_file}) ==="
    show_diff "$target_file" "$profile_template"

    if (( APPLY == 1 )); then
      install_rendered_file "$profile_template" "$target_file"
    fi
  done
  shopt -u nullglob

  shopt -s nullglob
  for target_file in "$target_dir"/*.config.toml; do
    profile_name="$(basename "$target_file")"
    [[ -e "${CANONICAL_DIR}/${profile_name}" ]] && continue

    log ""
    log "=== Orphaned Codex Profile (${target_file}) ==="
    show_diff "$target_file" /dev/null

    if (( APPLY == 1 )); then
      rm -f "$target_file"
      log "Removed: $target_file"
    fi
  done
  shopt -u nullglob
}

ensure_enabled_openai_bundled_plugins() {
  PYTHONPATH="$ROOT_DIR" python3 - "$PLUGIN_REGISTRY" "$HOME" <<'PY'
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from plugins.derived import validate_plugin_registry


plugin_registry = Path(sys.argv[1]).expanduser().resolve()
home = Path(sys.argv[2])
bundle_marketplace = Path(
    os.environ.get(
        "CODEX_BUNDLED_MARKETPLACE",
        "/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled",
    )
).expanduser()
runtime_cache = home / ".codex/plugins/cache/openai-bundled"
stale_runtime_marketplace = home / ".codex/.tmp/bundled-marketplaces/openai-bundled"
registry_data = json.loads(plugin_registry.read_text(encoding="utf-8"))
plugins, _, _ = validate_plugin_registry(
    registry_data,
    root_dir=plugin_registry.parent.parent,
    home=home,
)
enabled_plugin_names = [
    plugin.plugin
    for plugin in plugins
    if plugin.enabled and plugin.marketplace == "openai-bundled" and plugin.scope in {"global", "repo"}
]
enabled_plugin_name_set = set(enabled_plugin_names)


def tree_matches(source: Path, target: Path) -> bool:
    if source.is_symlink():
        return target.is_symlink() and os.readlink(source) == os.readlink(target)
    if source.is_dir():
        if not target.is_dir():
            return False
        source_children = {child.name: child for child in source.iterdir()}
        target_children = {child.name: child for child in target.iterdir()}
        if set(source_children) != set(target_children):
            return False
        return all(tree_matches(child, target / name) for name, child in source_children.items())
    if source.is_file():
        return target.is_file() and source.stat().st_size == target.stat().st_size
    return True


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def copy_entry_without_xattrs(source: Path, target: Path) -> None:
    if tree_matches(source, target):
        return

    if source.is_symlink():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            remove_path(target)
        os.symlink(os.readlink(source), target)
        return

    if source.is_dir():
        if target.exists() and not target.is_dir():
            remove_path(target)
        target.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copymode(source, target, follow_symlinks=False)
        except OSError:
            pass
        for child in source.iterdir():
            copy_entry_without_xattrs(child, target / child.name)
        return

    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_dir():
            remove_path(target)
        if target.exists() or target.is_symlink():
            target.unlink()
        shutil.copyfile(source, target, follow_symlinks=False)
        shutil.copymode(source, target, follow_symlinks=False)


def copy_plugin_tree(source: Path, target: Path) -> None:
    if tree_matches(source, target):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        remove_path(target)
    copy_entry_without_xattrs(source, target)
    if not tree_matches(source, target):
        raise RuntimeError(f"plugin copy incomplete: {source} -> {target}")


if stale_runtime_marketplace.exists():
    remove_path(stale_runtime_marketplace)
    print(f"Removed stale bundled marketplace mirror: {stale_runtime_marketplace}")

if not bundle_marketplace.is_dir():
    print(f"Warning: bundled plugin marketplace is missing: {bundle_marketplace}", file=sys.stderr)

if runtime_cache.is_dir():
    for cached_plugin in runtime_cache.iterdir():
        if cached_plugin.name not in enabled_plugin_name_set:
            remove_path(cached_plugin)
            print(f"Removed stale bundled plugin cache: {cached_plugin}")

for plugin_name in enabled_plugin_names:
    plugin_id = f"{plugin_name}@openai-bundled"
    source = bundle_marketplace / "plugins" / plugin_name
    manifest_path = source / ".codex-plugin/plugin.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"enabled bundled plugin source is missing for {plugin_id}: {source}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest.get("version") or "unknown")
    copy_plugin_tree(source, runtime_cache / plugin_name / version)

    print(f"Ensured: {plugin_id} {version}")
PY
}

log "Control Plane: $CONTROL_PLANE_DIR"
log "Canonical Dir: $CANONICAL_DIR"
if (( APPLY == 1 )); then
  log "Mode: APPLY"
else
  log "Mode: DRY-RUN (no files written)"
fi

if (( SYNC_GLOBAL == 1 )); then
  sync_global
  sync_profile_configs
fi
if (( APPLY == 1 )); then
  ensure_enabled_openai_bundled_plugins
fi

log ""
if (( APPLY == 1 )); then
  log "Done. Restart Codex to ensure new settings are loaded."
else
  log "Dry-run complete. Re-run with --apply to write changes."
fi
