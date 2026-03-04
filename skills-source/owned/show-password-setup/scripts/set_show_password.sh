#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "${SCRIPT_DIR}/../../../../" && pwd)}"

APP_NAME="${APP_NAME:-aipodcasting-app}"
VAULT_NAME="${VAULT_NAME:-kv-shared-repos}"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
MAPPING_FILE="${MAPPING_FILE:-${REPO_DIR}/scripts/local/secrets/keyvault_env_map.env}"
MAPPING_TEMPLATE_FILE="${MAPPING_TEMPLATE_FILE:-${REPO_DIR}/scripts/local/secrets/keyvault_env_map.env.example}"
BOOTSTRAP_SCRIPT="${BOOTSTRAP_SCRIPT:-${REPO_DIR}/scripts/local/secrets/bootstrap_local_env_from_keyvault.sh}"
AZ_BIN="${AZ_BIN:-/opt/homebrew/bin/az}"

if [[ ! -x "${AZ_BIN}" ]]; then
  AZ_BIN="$(command -v az || true)"
fi
if [[ -z "${AZ_BIN}" ]]; then
  echo "Azure CLI not found. Install az or set AZ_BIN." >&2
  exit 2
fi

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

prompt_secret() {
  local label="$1"
  local value=""
  read -r -s -p "${label}: " value
  echo
  printf "%s" "$value"
}

upsert_mapping() {
  local file_path="$1"
  local var_name="$2"
  local secret_name="$3"

  python3 - "$file_path" "$var_name" "$secret_name" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
env_var = sys.argv[2]
secret_name = sys.argv[3]

path.parent.mkdir(parents=True, exist_ok=True)
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

updated = False
next_lines = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        next_lines.append(line)
        continue
    key, _ = line.split("=", 1)
    if key.strip() == env_var:
        next_lines.append(f"{env_var}={secret_name}")
        updated = True
    else:
        next_lines.append(line)

if not updated:
    next_lines.append(f"{env_var}={secret_name}")

path.write_text("\\n".join(next_lines) + "\\n", encoding="utf-8")
PY
}

raw_show_name="$(prompt 'Show name (matches ?show= in URLs)')"
if [[ -z "$raw_show_name" ]]; then
  echo "Show name is required." >&2
  exit 1
fi

password_value="$(prompt_secret 'Password (stored in Key Vault)')"
if [[ -z "$password_value" ]]; then
  echo "Password is required." >&2
  exit 1
fi

show_id="$(
  echo "$raw_show_name" \
    | tr '[:lower:]' '[:upper:]' \
    | sed -E 's/[^A-Z0-9]+/_/g; s/^_+|_+$//g; s/_+/_/g'
)"
show_slug="$(echo "$show_id" | tr '[:upper:]' '[:lower:]' | tr '_' '-')"
env_var="PASSWORD_SHOW_${show_id}"
secret_name="aipodcasting-app--password-show-${show_slug}"
kv_ref="@Microsoft.KeyVault(SecretUri=https://${VAULT_NAME}.vault.azure.net/secrets/${secret_name}/)"

resource_group="${AZURE_RESOURCE_GROUP:-${AIPODCASTING_APP_RG:-}}"
if [[ -z "$resource_group" ]]; then
  resource_group="$("${AZ_BIN}" webapp list --query "[?name=='${APP_NAME}'].resourceGroup | [0]" -o tsv 2>/dev/null || true)"
fi
if [[ -z "$resource_group" ]]; then
  resource_group="$(prompt 'Azure resource group (for aipodcasting-app)' 'aipodcasting')"
fi
if [[ -z "$resource_group" ]]; then
  echo "Resource group is required." >&2
  exit 1
fi

echo "Writing secret ${secret_name} to Key Vault ${VAULT_NAME}..."
"${AZ_BIN}" keyvault secret set \
  --vault-name "${VAULT_NAME}" \
  --name "${secret_name}" \
  --value "${password_value}" >/dev/null

echo "Setting ${env_var} on ${APP_NAME} as Key Vault reference..."
"${AZ_BIN}" webapp config appsettings set \
  --name "${APP_NAME}" \
  --resource-group "${resource_group}" \
  --settings "${env_var}=${kv_ref}" >/dev/null

upsert_mapping "${MAPPING_FILE}" "${env_var}" "${secret_name}"
if [[ -f "${MAPPING_TEMPLATE_FILE}" ]]; then
  upsert_mapping "${MAPPING_TEMPLATE_FILE}" "${env_var}" "${secret_name}"
fi

if [[ -x "${BOOTSTRAP_SCRIPT}" ]]; then
  echo "Refreshing local .env from Key Vault mappings..."
  "${BOOTSTRAP_SCRIPT}" --vault-name "${VAULT_NAME}" --allow-missing >/dev/null
fi

echo "Done."
echo "Azure: ${env_var} set on ${APP_NAME} (resource group: ${resource_group}) via Key Vault reference"
echo "Key Vault: ${secret_name}"
echo "Local mapping: ${MAPPING_FILE}"
echo "Local env refreshed: ${ENV_FILE}"
