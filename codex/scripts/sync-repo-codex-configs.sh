#!/usr/bin/env bash
set -euo pipefail

APPLY=0
CHECK=0
REGISTRY_FILE=""
MCP_REGISTRY_FILE=""
HOOKS_REGISTRY_FILE=""
PLUGIN_REGISTRY_FILE=""
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"
DEFAULT_REGISTRY_FILE="${CONTROL_PLANE_DIR}/config/repo-bootstrap.json"
DEFAULT_MCP_REGISTRY_FILE="${ROOT_DIR}/mcp/config/presets.json"
DEFAULT_HOOKS_REGISTRY_FILE="${ROOT_DIR}/hooks/registry.json"
DEFAULT_PLUGIN_REGISTRY_FILE="${ROOT_DIR}/plugins/registry.json"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed repo-local Codex config files from the canonical registry.
Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diffs only (default)
  --check                Fail if rendered files differ from repo-local files
  --registry <path>      Override repo bootstrap registry
                         (default: codex/config/repo-bootstrap.json)
  --mcp-registry <path>  Override shared MCP registry
                         (default: mcp/config/presets.json)
  --hooks-registry <path>
                         Override shared hooks registry
                         (default: hooks/registry.json)
  --plugin-registry <path>
                         Override native Codex plugin registry
                         (default: plugins/registry.json)
  --repo <path>          Limit sync to an exact repo path (repeatable)
  -h, --help             Show this help

Examples:
  ~/GitHub/agents/codex/scripts/sync-repo-codex-configs.sh
  ~/GitHub/agents/codex/scripts/sync-repo-codex-configs.sh --apply
  ~/GitHub/agents/codex/scripts/sync-repo-codex-configs.sh --apply --repo ~/GitHub/win
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
    --mcp-registry)
      MCP_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --hooks-registry)
      HOOKS_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --plugin-registry)
      PLUGIN_REGISTRY_FILE="${2:-}"
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
if [[ -z "$MCP_REGISTRY_FILE" ]]; then
  MCP_REGISTRY_FILE="$DEFAULT_MCP_REGISTRY_FILE"
fi
if [[ -z "$HOOKS_REGISTRY_FILE" ]]; then
  HOOKS_REGISTRY_FILE="$DEFAULT_HOOKS_REGISTRY_FILE"
fi
if [[ -z "$PLUGIN_REGISTRY_FILE" ]]; then
  PLUGIN_REGISTRY_FILE="$DEFAULT_PLUGIN_REGISTRY_FILE"
fi
[[ -f "$REGISTRY_FILE" ]] || die "Missing registry file: $REGISTRY_FILE"
[[ -r "$REGISTRY_FILE" ]] || die "Registry file is not readable: $REGISTRY_FILE"
[[ -f "$MCP_REGISTRY_FILE" ]] || die "Missing MCP registry file: $MCP_REGISTRY_FILE"
[[ -r "$MCP_REGISTRY_FILE" ]] || die "MCP registry file is not readable: $MCP_REGISTRY_FILE"
[[ -f "$HOOKS_REGISTRY_FILE" ]] || die "Missing hooks registry file: $HOOKS_REGISTRY_FILE"
[[ -r "$HOOKS_REGISTRY_FILE" ]] || die "Hooks registry file is not readable: $HOOKS_REGISTRY_FILE"
[[ -f "$PLUGIN_REGISTRY_FILE" ]] || die "Missing plugin registry file: $PLUGIN_REGISTRY_FILE"
[[ -r "$PLUGIN_REGISTRY_FILE" ]] || die "Plugin registry file is not readable: $PLUGIN_REGISTRY_FILE"

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

is_drifted() {
  local target="$1"
  local rendered="$2"

  [[ ! -f "$target" ]] || ! cmp -s "$target" "$rendered"
}

MANIFEST_FILE="${TMP_DIR}/manifest.tsv"
PYTHONPATH="$ROOT_DIR" python3 - "$REGISTRY_FILE" "$MCP_REGISTRY_FILE" "$HOOKS_REGISTRY_FILE" "$PLUGIN_REGISTRY_FILE" "$TMP_DIR" ${REPO_FILTERS[@]+"${REPO_FILTERS[@]}"} >"$MANIFEST_FILE" <<'PY'
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

CLIENT_OWNED_THREAD_SELECTION_KEYS = {
    "model",
    "model_auto_compact_token_limit",
    "model_provider",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "plan_mode_reasoning_effort",
    "profile",
    "service_tier",
}

REPO_SCALAR_KEYS = [
    "model_instructions_file",
    "developer_instructions",
    "project_root_markers",
    "web_search",
    "approval_policy",
    "sandbox_mode",
    "personality",
]


def reject_client_owned_thread_selection(values: dict, scope: str) -> None:
    forbidden = sorted(CLIENT_OWNED_THREAD_SELECTION_KEYS.intersection(values))
    features = values.get("features")
    if isinstance(features, dict) and "fast_mode" in features:
        forbidden.append("features.fast_mode")
    if forbidden:
        raise TypeError(
            f"{scope} sets client-owned thread selection: {', '.join(forbidden)}"
        )


def normalize_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        if "\n" in value:
            escaped = value.replace('"""', '\\"""').rstrip("\n")
            return f'"""\n{escaped}\n"""'
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


def codex_mcp_config(name: str, preset: dict) -> dict:
    transport = preset.get("transport")
    if transport == "http":
        return {key: value for key, value in preset.items() if key != "transport"}
    if transport == "stdio":
        return {key: value for key, value in preset.items() if key != "transport"}
    raise TypeError(f"Unsupported MCP transport for `{name}`: {transport}")


def render_repo_config(
    repo: str,
    defaults: dict,
    override: dict,
    mcp_assignments: list[tuple[str, dict]],
    repo_plugins: list,
) -> str:
    lines = [
        "# Managed by ~/GitHub/agents/codex/scripts/sync-repo-codex-configs.sh.",
        "# Edit ~/GitHub/agents/codex/config/repo-bootstrap.json and re-run the sync script.",
    ]
    rendered_anything = False

    scalar_lines = []
    for key in REPO_SCALAR_KEYS:
        value = override.get(key, defaults.get(key))
        if value is not None:
            scalar_lines.append(f"{key} = {toml_value(value)}")
    if scalar_lines:
        rendered_anything = True
        lines.append("")
        lines.extend(scalar_lines)

    default_features = defaults.get("features", {})
    override_features = override.get("features", {})
    if default_features and not isinstance(default_features, dict):
        raise TypeError("defaults.features must be a table")
    if override_features and not isinstance(override_features, dict):
        raise TypeError(f"features for {repo} must be a table")

    features = dict(default_features)
    features.update(override_features)
    if features:
        rendered_anything = True
        lines.append("")
        lines.append("[features]")
        for key in sorted(features):
            lines.append(f"{key} = {toml_value(features[key])}")

    for plugin in sorted(repo_plugins, key=lambda item: item.plugin_id):
        rendered_anything = True
        lines.append("")
        lines.append(f'[plugins."{plugin.plugin_id}"]')
        lines.append(f"enabled = {toml_value(plugin.enabled)}")

    for preset_name, preset in mcp_assignments:
        codex_config = codex_mcp_config(preset_name, preset)
        rendered_anything = True
        lines.append("")
        lines.append(f"[mcp_servers.{preset_name}]")
        for key in sorted(codex_config):
            lines.append(f"{key} = {toml_value(codex_config[key])}")

    if not rendered_anything:
        lines.append("# No repo-local Codex overrides are currently assigned.")

    return "\n".join(lines) + "\n"

registry_path = Path(sys.argv[1]).expanduser().resolve()
mcp_registry_path = Path(sys.argv[2]).expanduser().resolve()
hooks_registry_path = Path(sys.argv[3]).expanduser().resolve()
plugin_registry_path = Path(sys.argv[4]).expanduser().resolve()
tmp_dir = Path(sys.argv[5]).resolve()
filters = {normalize_path(path) for path in sys.argv[6:] if path}

root_dir = registry_path.parent.parent.parent.resolve()
sys.path.insert(0, str(root_dir))

from hooks.control_plane import load_hooks_registry, render_codex_hooks
from mcp.control_plane import load_mcp_catalog
from plugins.derived import resolve_repo_root, validate_plugin_registry


data = json.loads(registry_path.read_text(encoding="utf-8"))
defaults = data.get("defaults", {})
repos_raw = data.get("repos", [])
mcp_catalog = load_mcp_catalog(mcp_registry_path, repos_raw)
hooks_registry = load_hooks_registry(hooks_registry_path)
plugin_registry_data = json.loads(plugin_registry_path.read_text(encoding="utf-8"))
plugins, _unmanaged_plugins, plugin_github_root = validate_plugin_registry(
    plugin_registry_data,
    root_dir=plugin_registry_path.parent.parent,
    home=Path.home(),
)

if not isinstance(defaults, dict):
    raise TypeError("defaults must be an object")
if not isinstance(repos_raw, list):
    raise TypeError("repos must be an array")
reject_client_owned_thread_selection(defaults, "defaults")
for index, item in enumerate(repos_raw):
    if isinstance(item, dict):
        reject_client_owned_thread_selection(item, f"repos[{index}]")

repo_items_all: list[dict] = []
for item in repos_raw:
    if not isinstance(item, dict):
        raise TypeError("each repo entry must be an object")
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise TypeError("repo.path must be a non-empty string")
    repo_path = Path(normalize_path(raw_path))
    if filters and str(repo_path) not in filters:
        continue
    try:
        actual_repo = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        if repo_path.exists():
            print(f"WARNING: skipping existing non-git path: {repo_path}", file=sys.stderr)
        continue

    actual_repo = str(Path(actual_repo).resolve())
    repo_name = Path(actual_repo).name or actual_repo
    repo_copy = dict(item)
    repo_copy["_actual_repo"] = actual_repo
    repo_copy["_repo_name"] = repo_name
    repo_items_all.append(repo_copy)

repo_plugins_by_root: dict[str, list] = {item["_actual_repo"]: [] for item in repo_items_all}
for plugin in plugins:
    if plugin.scope != "repo":
        continue
    for repo_ref in plugin.repos:
        repo_root = str(resolve_repo_root(repo_ref, plugin_github_root, Path.home()))
        if repo_root in repo_plugins_by_root:
            repo_plugins_by_root[repo_root].append(plugin)

manifest_lines: list[str] = []
managed_header = "# Managed by ~/GitHub/agents/codex/scripts/sync-repo-codex-configs.sh."
for item in repo_items_all:
    actual_repo = item["_actual_repo"]
    if filters and actual_repo not in filters:
        continue

    expected_role_targets: set[Path] = set()

    rendered = render_repo_config(
        actual_repo,
        defaults,
        item,
        mcp_catalog.presets_for(item["path"], "codex"),
        repo_plugins_by_root.get(actual_repo, []),
    )
    rendered_path = tmp_dir / f"{hashlib.sha256(actual_repo.encode()).hexdigest()}.toml"
    rendered_path.write_text(rendered, encoding="utf-8")
    target_path = Path(actual_repo) / ".codex" / "config.toml"
    manifest_lines.append(f"{actual_repo}\t{target_path}\t{rendered_path}")

    rendered_hooks = render_codex_hooks(hooks_registry, repo_name=item["_repo_name"])
    rendered_hooks_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':hooks').encode()).hexdigest()}.json"
    rendered_hooks_path.write_text(
        json.dumps(rendered_hooks, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    target_hooks_path = Path(actual_repo) / ".codex" / "hooks.json"
    manifest_lines.append(f"{actual_repo}\t{target_hooks_path}\t{rendered_hooks_path}")

    agents_dir = Path(actual_repo) / ".codex" / "agents"
    if agents_dir.is_dir():
        for existing_role_path in sorted(agents_dir.glob("*.toml")):
            if existing_role_path.resolve() in expected_role_targets:
                continue
            try:
                first_line = existing_role_path.read_text(encoding="utf-8").splitlines()[0]
            except (IndexError, UnicodeDecodeError, OSError):
                continue
            if first_line == managed_header:
                manifest_lines.append(f"{actual_repo}\t{existing_role_path}\t__DELETE__")

for line in manifest_lines:
    print(line)
PY

MANIFEST=()
while IFS= read -r line; do
  if [[ -n "$line" ]]; then
    MANIFEST+=("$line")
  fi
done <"$MANIFEST_FILE"

if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed repo configs were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed repo-local Codex files from ${REGISTRY_FILE}."

DRIFT=0
for entry in ${MANIFEST[@]+"${MANIFEST[@]}"}; do
  IFS=$'\t' read -r repo target rendered <<<"$entry"

  log ""
  log "=== Repo Codex File (${repo}) ==="
  log "Target: $target"
  if [[ "$rendered" == "__DELETE__" ]]; then
    log "Stale managed repo agent role file will be removed."
    show_diff "$target" /dev/null
  else
    show_diff "$target" "$rendered"
  fi

  if [[ "$rendered" == "__DELETE__" ]] || is_drifted "$target" "$rendered"; then
    DRIFT=1
  fi

  if (( APPLY == 1 )); then
    if [[ "$rendered" == "__DELETE__" ]]; then
      rm -f "$target"
      log "Removed: $target"
    else
      ensure_parent_dir "$target"
      install_rendered_file "$rendered" "$target"
    fi
  fi
done

if (( CHECK == 1 )); then
  if (( DRIFT == 1 )); then
    printf 'ERROR: repo-local Codex files are out of sync. Re-run sync-repo-codex-configs.sh --apply for the affected repo(s).\n' >&2
    exit 1
  fi
  log "OK: repo-local Codex files are in sync."
fi
