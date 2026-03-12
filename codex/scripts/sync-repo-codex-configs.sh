#!/usr/bin/env bash
set -euo pipefail

APPLY=0
REGISTRY_FILE=""
REPO_FILTERS=()
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_REGISTRY_FILE="${CONTROL_PLANE_DIR}/config/repo-bootstrap.toml"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed repo-local .codex/config.toml files from the canonical registry.
Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diffs only (default)
  --registry <path>      Override repo bootstrap registry
                         (default: codex/config/repo-bootstrap.toml)
  --repo <path>          Limit sync to an exact repo path (repeatable)
  -h, --help             Show this help

Examples:
  ~/.agents/codex/scripts/sync-repo-codex-configs.sh
  ~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply
  ~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply --repo ~/GitHub/win
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
    --registry)
      REGISTRY_FILE="${2:-}"
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

[[ -f "$REGISTRY_FILE" ]] || die "Missing registry file: $REGISTRY_FILE"
[[ -r "$REGISTRY_FILE" ]] || die "Registry file is not readable: $REGISTRY_FILE"

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
  local backup="${target}.bak.${TIMESTAMP}"
  local mode="600"

  if [[ -f "$target" ]]; then
    mode="$(stat -f "%Lp" "$target" 2>/dev/null || echo 600)"
    cp "$target" "$backup"
    log "Backup: $backup"
  fi

  install -m "$mode" "$rendered" "$target"
  log "Updated: $target"
}

mapfile -t MANIFEST < <(
  python3 - "$REGISTRY_FILE" "$TMP_DIR" "${REPO_FILTERS[@]}" <<'PY'
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


def normalize_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def discover_repo_roots(root: Path) -> list[str]:
    seen: set[str] = set()
    if not root.is_dir():
        return []
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
        if repo_root:
            seen.add(str(Path(repo_root).resolve()))
    return sorted(seen)


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
    raise TypeError(f"Unsupported TOML value: {value!r}")


def render_repo_config(repo: str, override: dict, presets: dict) -> str:
    lines = [
        "# Managed by ~/.agents/codex/scripts/sync-repo-codex-configs.sh.",
        "# Edit ~/.agents/codex/config/repo-bootstrap.toml and re-run the sync script.",
        f"# Repo: {repo}",
    ]

    scalar_keys = [
        "profile",
        "model",
        "model_reasoning_effort",
        "model_reasoning_summary",
        "model_verbosity",
        "web_search",
        "approval_policy",
        "sandbox_mode",
        "personality",
        "service_tier",
    ]

    scalar_lines = []
    for key in scalar_keys:
        if key in override:
            scalar_lines.append(f"{key} = {toml_value(override[key])}")
    if scalar_lines:
        lines.append("")
        lines.extend(scalar_lines)

    features = override.get("features")
    if features:
        if not isinstance(features, dict):
            raise TypeError(f"features for {repo} must be a table")
        lines.append("")
        lines.append("[features]")
        for key, value in features.items():
            lines.append(f"{key} = {toml_value(value)}")

    preset_names = override.get("mcp_presets", [])
    if not isinstance(preset_names, list):
        raise TypeError(f"mcp_presets for {repo} must be an array")

    for preset_name in preset_names:
        if preset_name not in presets:
            raise KeyError(f"Unknown MCP preset `{preset_name}` for {repo}")
        preset = presets[preset_name]
        if not isinstance(preset, dict):
            raise TypeError(f"MCP preset `{preset_name}` must be a table")
        lines.append("")
        lines.append(f"[mcp_servers.{preset_name}]")
        for key, value in preset.items():
            lines.append(f"{key} = {toml_value(value)}")

    return "\n".join(lines) + "\n"


registry_path = Path(sys.argv[1]).expanduser().resolve()
tmp_dir = Path(sys.argv[2]).resolve()
filters = {normalize_path(path) for path in sys.argv[3:] if path}

data = tomllib.loads(registry_path.read_text(encoding="utf-8"))
discovery = data.get("discovery", {})
presets = data.get("mcp_presets", {})
repo_overrides_raw = data.get("repos", {})

if not isinstance(discovery, dict):
    raise TypeError("discovery must be a table")
if not isinstance(presets, dict):
    raise TypeError("mcp_presets must be a table")
if not isinstance(repo_overrides_raw, dict):
    raise TypeError("repos must be a table keyed by repo path")

roots = [normalize_path(path) for path in discovery.get("roots", [])]
extra_repos = [normalize_path(path) for path in discovery.get("extra_repos", [])]

managed_repos: set[str] = set()
for root in roots:
    managed_repos.update(discover_repo_roots(Path(root)))
managed_repos.update(extra_repos)

repo_overrides = {normalize_path(path): value for path, value in repo_overrides_raw.items()}
managed_repos.update(repo_overrides.keys())

if filters:
    managed_repos = {repo for repo in managed_repos if repo in filters}

if not managed_repos:
    raise SystemExit("No managed repos resolved from the configured registry and filters.")

manifest_lines: list[str] = []
for repo in sorted(managed_repos):
    repo_path = Path(repo)
    if not repo_path.exists():
        print(f"WARNING: skipping missing repo path: {repo}", file=sys.stderr)
        continue
    try:
        actual_repo = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(f"WARNING: skipping non-git path: {repo}", file=sys.stderr)
        continue

    actual_repo = str(Path(actual_repo).resolve())
    if filters and actual_repo not in filters:
        continue

    override = repo_overrides.get(actual_repo, {})
    if not isinstance(override, dict):
        raise TypeError(f"repo override for {actual_repo} must be a table")

    rendered = render_repo_config(actual_repo, override, presets)
    rendered_path = tmp_dir / f"{hashlib.sha256(actual_repo.encode()).hexdigest()}.toml"
    rendered_path.write_text(rendered, encoding="utf-8")
    target_path = Path(actual_repo) / ".codex" / "config.toml"
    manifest_lines.append(f"{actual_repo}\t{target_path}\t{rendered_path}")

for line in manifest_lines:
    print(line)
PY
)

if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed repo configs were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed repo-local Codex configs from ${REGISTRY_FILE}."

for entry in "${MANIFEST[@]}"; do
  IFS=$'\t' read -r repo target rendered <<<"$entry"
  ensure_parent_dir "$target"

  log ""
  log "=== Repo Codex Config (${repo}) ==="
  show_diff "$target" "$rendered"

  if (( APPLY == 1 )); then
    install_rendered_file "$rendered" "$target"
  fi
done
