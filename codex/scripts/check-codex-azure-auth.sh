#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${HOME}/.codex/config.toml"
SECRET_ENV_FILE="${HOME}/.secrets/azure-openai/env"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Check whether this machine can authenticate Codex to Azure OpenAI.

Options:
  --config <path>      Codex config to inspect (default: ~/.codex/config.toml)
  --env-file <path>    Machine-local env file (default: ~/.secrets/azure-openai/env)
  -h, --help           Show this help

This is a local readiness check. It never prints the API key.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_FILE="${2:-}"
      shift 2
      ;;
    --env-file)
      SECRET_ENV_FILE="${2:-}"
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

if [[ -z "${AZURE_OPENAI_API_KEY:-}" && -r "$SECRET_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$SECRET_ENV_FILE"
fi

python3 - "$CONFIG_FILE" <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


config_path = Path(sys.argv[1]).expanduser()


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
if provider_name != "azure-key":
    fail(f"Codex model_provider is {provider_name!r}, expected 'azure-key'")

providers = config.get("model_providers")
if not isinstance(providers, dict):
    fail("missing [model_providers] table")
azure_key = providers.get("azure-key")
if not isinstance(azure_key, dict):
    fail("missing [model_providers.azure-key] table")

if "auth" in azure_key:
    fail("[model_providers.azure-key] must not use command-backed auth")

env_key = azure_key.get("env_key")
if env_key != "AZURE_OPENAI_API_KEY":
    fail(f"Azure API-key provider env_key is {env_key!r}, expected 'AZURE_OPENAI_API_KEY'")

if not os.environ.get("AZURE_OPENAI_API_KEY"):
    fail("AZURE_OPENAI_API_KEY is not available. Run machine-secret sync and restart Codex Desktop.")

print(f"OK: Codex Azure API-key auth ready for model={model} provider=azure-key env_key=AZURE_OPENAI_API_KEY")
PY
