#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-aipodcasting-app}"
ENV_FILE="${ENV_FILE:-$HOME/GitHub/aipodcasting/.env}"

prompt() {
  local label="$1"
  local default_value="${2:-}"
  local value=""
  if [[ -n "$default_value" ]]; then
    read -r -p "${label} [${default_value}]: " value
    if [[ -z "$value" ]]; then
      value="$default_value"
    fi
  else
    read -r -p "${label}: " value
  fi
  printf "%s" "$value"
}

raw_show_name="$(prompt 'Show name (matches ?show= in URLs)')"
if [[ -z "$raw_show_name" ]]; then
  echo "Show name is required."
  exit 1
fi

password_value="$(prompt 'Password (will be stored in Azure + .env)')"
if [[ -z "$password_value" ]]; then
  echo "Password is required."
  exit 1
fi

show_id="$(
  echo "$raw_show_name" | tr '[:lower:]' '[:upper:]' | sed -E 's/[^A-Z0-9]+/_/g; s/^_+|_+$//g; s/_+/_/g'
)"
env_var="PASSWORD_SHOW_${show_id}"

resource_group="${AZURE_RESOURCE_GROUP:-${AIPODCASTING_APP_RG:-}}"
if [[ -z "$resource_group" ]]; then
  resource_group="$(az webapp list --query "[?name=='${APP_NAME}'].resourceGroup | [0]" -o tsv 2>/dev/null || true)"
fi
if [[ -z "$resource_group" ]]; then
  resource_group="$(prompt 'Azure resource group (for aipodcasting-app)')"
fi
if [[ -z "$resource_group" ]]; then
  echo "Resource group is required."
  exit 1
fi

echo "Setting ${env_var} in Azure App Service (${APP_NAME})..."
az webapp config appsettings set \
  --name "${APP_NAME}" \
  --resource-group "${resource_group}" \
  --settings "${env_var}=${password_value}" >/dev/null

python3 - <<PY
from __future__ import annotations

from pathlib import Path

env_file = Path("${ENV_FILE}")
env_file.parent.mkdir(parents=True, exist_ok=True)
env_var = "${env_var}"
value = "${password_value}"

lines = []
if env_file.exists():
    lines = env_file.read_text().splitlines()

updated = False
next_lines = []
for line in lines:
    if line.startswith(env_var + "="):
        next_lines.append(f'{env_var}="{value}"')
        updated = True
    else:
        next_lines.append(line)

if not updated:
    next_lines.append(f'{env_var}="{value}"')

env_file.write_text("\\n".join(next_lines) + "\\n")
PY

echo "Done."
echo "Azure: ${env_var} set on ${APP_NAME} (resource group: ${resource_group})"
echo "Local: ${ENV_FILE} updated"
