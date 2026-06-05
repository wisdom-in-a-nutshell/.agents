#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

CANONICAL_CONFIG="${CONTROL_PLANE_DIR}/config/global.config.toml"
GLOBAL_CONFIG="${HOME}/.codex/config.toml"
GLOBAL_HOOKS="${HOME}/.codex/hooks.json"
GITHUB_ROOT="${HOME}/GitHub"
SYNC_CONFIG_SCRIPT="${SCRIPT_DIR}/sync-config.sh"
CHECK_CONTROL_PLANE_SCRIPT="${SCRIPT_DIR}/check-codex-control-plane.sh"

APPLY=0
RUN_SYNC=1
RUN_CHECK=1
MODE=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [status|chatgpt|azure] [options]

Switch the managed global Codex default between the OpenAI ChatGPT
account provider and the Azure OpenAI API-key provider.

Default mode is status/dry-run. Use --apply to write changes.

Options:
  --apply                  Apply the switch and sync ~/.codex/config.toml
  --dry-run                Show the planned canonical config diff
  --no-sync                Update only the canonical config
  --no-check               Skip Codex control-plane validation after sync
  --canonical-config <p>   Override canonical global.config.toml
  --global-config <p>      Override ~/.codex/config.toml target
  --global-hooks <p>       Override ~/.codex/hooks.json target
  --github-root <path>     Override ~/GitHub root for sync-config
  -h, --help               Show this help

Examples:
  ~/GitHub/agents/codex/scripts/switch-codex-subscription.sh status
  ~/GitHub/agents/codex/scripts/switch-codex-subscription.sh chatgpt --apply
  ~/GitHub/agents/codex/scripts/switch-codex-subscription.sh azure --apply

One-off runs can use the synced profiles without changing the global default:
  codex --profile chatgpt
  codex --profile azure-openai
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
  if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    status|chatgpt|openai|default|azure)
      [[ -z "$MODE" ]] || die "Mode already set to $MODE"
      MODE="$1"
      shift
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --no-sync)
      RUN_SYNC=0
      shift
      ;;
    --no-check)
      RUN_CHECK=0
      shift
      ;;
    --canonical-config)
      CANONICAL_CONFIG="${2:-}"
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
    --github-root)
      GITHUB_ROOT="${2:-}"
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

MODE="${MODE:-status}"
if [[ "$MODE" == "openai" || "$MODE" == "default" ]]; then
  MODE="chatgpt"
fi

[[ -f "$CANONICAL_CONFIG" ]] || die "Missing canonical config: $CANONICAL_CONFIG"
[[ -x "$SYNC_CONFIG_SCRIPT" ]] || die "Missing executable: $SYNC_CONFIG_SCRIPT"
[[ -x "$CHECK_CONTROL_PLANE_SCRIPT" ]] || die "Missing executable: $CHECK_CONTROL_PLANE_SCRIPT"

TMP_DIR="$(mktemp -d)"
RENDERED_CONFIG="${TMP_DIR}/global.config.toml"

render_status() {
  python3 - "$CANONICAL_CONFIG" "$GLOBAL_CONFIG" "${HOME}/.codex/auth.json" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def provider_for(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "missing", "missing"
    text = path.read_text(encoding="utf-8")
    current_section = None
    provider = None
    has_azure_key = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped
            if stripped == "[model_providers.azure-key]":
                has_azure_key = True
            continue
        if current_section is None:
            match = re.match(r'^model_provider\s*=\s*"([^"]+)"\s*$', stripped)
            if match:
                provider = match.group(1)
    if provider == "azure-key":
        mode = "azure"
    elif provider is None:
        mode = "chatgpt"
    else:
        mode = f"custom:{provider}"
    detail = "azure provider block present" if has_azure_key else "no azure provider block"
    return mode, detail


canonical, canonical_detail = provider_for(Path(sys.argv[1]).expanduser())
runtime, runtime_detail = provider_for(Path(sys.argv[2]).expanduser())

auth_path = Path(sys.argv[3]).expanduser()
auth_mode = "missing"
if auth_path.exists():
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        auth_mode = str(auth.get("auth_mode", "unknown"))
    except Exception:
        auth_mode = "unreadable"

print(f"canonical: {canonical} ({canonical_detail})")
print(f"runtime:   {runtime} ({runtime_detail})")
print(f"auth:      {auth_mode}")
PY
}

render_config() {
  python3 - "$CANONICAL_CONFIG" "$RENDERED_CONFIG" "$MODE" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


source = Path(sys.argv[1]).expanduser()
target = Path(sys.argv[2]).expanduser()
mode = sys.argv[3]

azure_block = [
    "[model_providers.azure-key]",
    'name = "Azure"',
    'base_url = "https://aip-openai.openai.azure.com/openai/v1"',
    'env_key = "AZURE_OPENAI_API_KEY"',
    'wire_api = "responses"',
]

lines = source.read_text(encoding="utf-8").splitlines()


def is_header(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("[") and stripped.endswith("]")


def remove_azure_provider_block(input_lines: list[str]) -> list[str]:
    output: list[str] = []
    i = 0
    while i < len(input_lines):
        stripped = input_lines[i].strip()
        if stripped == "[model_providers.azure-key]":
            i += 1
            while i < len(input_lines) and not is_header(input_lines[i]):
                i += 1
            while output and output[-1] == "" and (i >= len(input_lines) or input_lines[i].strip() == ""):
                output.pop()
            continue
        output.append(input_lines[i])
        i += 1
    return output


def remove_top_level_model_provider(input_lines: list[str]) -> list[str]:
    output: list[str] = []
    in_top_level = True
    for line in input_lines:
        if is_header(line):
            in_top_level = False
        if in_top_level and re.match(r"^\s*model_provider\s*=", line):
            continue
        output.append(line)
    return output


def add_top_level_model_provider(input_lines: list[str]) -> list[str]:
    output: list[str] = []
    inserted = False
    in_top_level = True
    for line in input_lines:
        if in_top_level and not inserted and re.match(r"^\s*model\s*=", line):
            output.append(line)
            output.append('model_provider = "azure-key"')
            inserted = True
            continue
        if is_header(line):
            if in_top_level and not inserted:
                output.append('model_provider = "azure-key"')
                inserted = True
            in_top_level = False
        output.append(line)
    if not inserted:
        output.insert(0, 'model_provider = "azure-key"')
    return output


def collapse_blank_lines(input_lines: list[str]) -> list[str]:
    output: list[str] = []
    blank_count = 0
    for line in input_lines:
        if line == "":
            blank_count += 1
            if blank_count <= 2:
                output.append(line)
            continue
        blank_count = 0
        output.append(line)
    while output and output[-1] == "":
        output.pop()
    return output


lines = remove_azure_provider_block(lines)
lines = remove_top_level_model_provider(lines)

if mode == "azure":
    lines = add_top_level_model_provider(lines)
    lines = collapse_blank_lines(lines)
    lines.extend(["", *azure_block])
elif mode == "chatgpt":
    lines = collapse_blank_lines(lines)
else:
    raise SystemExit(f"unknown mode: {mode}")

target.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

if [[ "$MODE" == "status" ]]; then
  render_status
  exit 0
fi

render_config

if cmp -s "$CANONICAL_CONFIG" "$RENDERED_CONFIG"; then
  log "No canonical change needed for mode: $MODE"
else
  log "Planned canonical change for mode: $MODE"
  diff -u "$CANONICAL_CONFIG" "$RENDERED_CONFIG" || true
fi

if (( APPLY == 0 )); then
  log "Dry run only. Re-run with --apply to switch."
  exit 0
fi

if ! cmp -s "$CANONICAL_CONFIG" "$RENDERED_CONFIG"; then
  mode_bits="$(stat -f "%Lp" "$CANONICAL_CONFIG" 2>/dev/null || echo 600)"
  install -m "$mode_bits" "$RENDERED_CONFIG" "$CANONICAL_CONFIG"
  log "Updated: $CANONICAL_CONFIG"
fi

if (( RUN_SYNC == 1 )); then
  sync_cmd=(
    "$SYNC_CONFIG_SCRIPT"
    --apply
    --github-root "$GITHUB_ROOT"
    --global-config "$GLOBAL_CONFIG"
    --global-hooks "$GLOBAL_HOOKS"
  )
  log "+ ${sync_cmd[*]}"
  "${sync_cmd[@]}"
fi

if (( RUN_CHECK == 1 )); then
  check_cmd=(
    "$CHECK_CONTROL_PLANE_SCRIPT"
    --global-config "$GLOBAL_CONFIG"
    --global-hooks "$GLOBAL_HOOKS"
  )
  log "+ ${check_cmd[*]}"
  "${check_cmd[@]}"
fi

render_status
