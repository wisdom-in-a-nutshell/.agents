#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${HOME}/.codex/config.toml"
EXPECTED_SCOPE="https://cognitiveservices.azure.com/.default"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Check whether this machine can authenticate Codex to Azure OpenAI.

Options:
  --config <path>      Codex config to inspect (default: ~/.codex/config.toml)
  -h, --help           Show this help

This is a local readiness check. It never prints the access token.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_FILE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

python3 - "$CONFIG_FILE" "$EXPECTED_SCOPE" <<'PY'
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


config_path = Path(sys.argv[1]).expanduser()
expected_scope = sys.argv[2]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def warn_skip(message: str) -> None:
    print(f"SKIP: {message}")
    raise SystemExit(0)


if not config_path.is_file():
    fail(f"missing Codex config: {config_path}")

try:
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
except Exception as exc:
    fail(f"invalid TOML in {config_path}: {exc}")

provider_name = config.get("model_provider")
model = config.get("model", "<unset>")
if provider_name != "azure":
    warn_skip(f"Codex model_provider is {provider_name!r}, not 'azure'")

providers = config.get("model_providers")
if not isinstance(providers, dict):
    fail("missing [model_providers] table")
azure = providers.get("azure")
if not isinstance(azure, dict):
    fail("missing [model_providers.azure] table")

auth = azure.get("auth")
if not isinstance(auth, dict):
    fail("missing [model_providers.azure.auth] table")

command = auth.get("command")
args = auth.get("args")
timeout_ms = auth.get("timeout_ms", 10000)
if command != "az":
    fail(f"Azure provider auth command is {command!r}, expected 'az'")
if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
    fail("Azure provider auth args must be a string array")
if expected_scope not in args:
    fail(f"Azure provider auth args do not include scope {expected_scope}")
if shutil.which(command) is None:
    fail("Azure CLI is not installed or not on PATH. Install azure-cli, then run az login.")

account = subprocess.run(
    [command, "account", "show", "--query", "{name:name,id:id,tenantId:tenantId,user:user.name}", "-o", "json"],
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
if account.returncode != 0:
    detail = account.stderr.strip() or account.stdout.strip()
    fail(f"Azure CLI is not authenticated. Run az login on this machine. Detail: {detail}")

timeout_seconds = max(1, int(timeout_ms) / 1000)
token = subprocess.run(
    [command, *args],
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    timeout=timeout_seconds,
)
if token.returncode != 0:
    detail = token.stderr.strip() or token.stdout.strip()
    fail(f"Azure OpenAI token mint failed. Detail: {detail}")
if not token.stdout.strip():
    fail("Azure OpenAI token mint returned an empty token")

print(f"OK: Codex Azure auth ready for model={model} provider=azure scope={expected_scope}")
PY
