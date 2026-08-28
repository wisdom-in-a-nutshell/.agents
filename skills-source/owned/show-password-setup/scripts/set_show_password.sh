#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "${SCRIPT_DIR}/../../../../" && pwd)}"

VAULT_NAME="${VAULT_NAME:-kv-shared-repos}"
LOCAL_SECRETS_BIN="${LOCAL_SECRETS_BIN:-${HOME}/GitHub/scripts/bin/local-secrets}"
ENV_FILE="${ENV_FILE:-${REPO_DIR}/.env}"
MAPPING_FILE="${MAPPING_FILE:-${REPO_DIR}/scripts/local/secrets/keyvault_env_map.env}"
MAPPING_TEMPLATE_FILE="${MAPPING_TEMPLATE_FILE:-${REPO_DIR}/scripts/local/secrets/keyvault_env_map.env.example}"
BOOTSTRAP_SCRIPT="${BOOTSTRAP_SCRIPT:-${REPO_DIR}/scripts/local/secrets/bootstrap_local_env_from_keyvault.sh}"
RUNTIME_USER="${USER:-$(id -un)}"
SERVICE_LABEL="${SERVICE_LABEL:-com.${RUNTIME_USER}.aipodcasting-app}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8800/api/health}"
RELOAD_SERVICE="${RELOAD_SERVICE:-1}"

if [[ ! -x "${LOCAL_SECRETS_BIN}" ]]; then
  echo "Missing local secret-store client: ${LOCAL_SECRETS_BIN}" >&2
  exit 2
fi
if [[ ! -x "${BOOTSTRAP_SCRIPT}" ]]; then
  echo "Missing executable env bootstrap: ${BOOTSTRAP_SCRIPT}" >&2
  exit 2
fi
if [[ ! -f "${MAPPING_TEMPLATE_FILE}" ]]; then
  echo "Missing tracked env mapping contract: ${MAPPING_TEMPLATE_FILE}" >&2
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

password_value="$(prompt_secret 'Password (stored in the local secret store)')"
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

echo "Writing secret ${secret_name} to local scope ${VAULT_NAME}..."
printf '%s' "${password_value}" | "${LOCAL_SECRETS_BIN}" --plain set \
  --vault "${VAULT_NAME}" \
  --name "${secret_name}" \
  --stdin \
  --apply >/dev/null

upsert_mapping "${MAPPING_FILE}" "${env_var}" "${secret_name}"
upsert_mapping "${MAPPING_TEMPLATE_FILE}" "${env_var}" "${secret_name}"

echo "Refreshing local .env from local secret mappings..."
"${BOOTSTRAP_SCRIPT}" --vault-name "${VAULT_NAME}" --allow-missing >/dev/null

service_status="not installed"
service_domain="gui/$(id -u)"
if [[ "${RELOAD_SERVICE}" == "1" ]] && launchctl print "${service_domain}/${SERVICE_LABEL}" >/dev/null 2>&1; then
  echo "Restarting ${SERVICE_LABEL} to load the refreshed runtime environment..."
  launchctl kickstart -k "${service_domain}/${SERVICE_LABEL}"
  service_status="health timeout"
  for _ in {1..60}; do
    if curl -fsS --max-time 5 "${HEALTH_URL}" >/dev/null 2>&1; then
      service_status="healthy"
      break
    fi
    sleep 1
  done
  if [[ "${service_status}" != "healthy" ]]; then
    echo "Local production frontend did not recover at ${HEALTH_URL}." >&2
    exit 1
  fi
elif [[ "${RELOAD_SERVICE}" != "1" ]]; then
  service_status="reload disabled"
fi

echo "Done."
echo "Runtime env: ${env_var}"
echo "Local secret: ${VAULT_NAME}/${secret_name}"
echo "Local mapping: ${MAPPING_FILE}"
echo "Local env refreshed: ${ENV_FILE}"
echo "Local service: ${service_status}"
