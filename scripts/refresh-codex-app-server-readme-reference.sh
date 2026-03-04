#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_DIR="${REPO_ROOT}/skills-source/owned/codex-app-server"

SOURCE_URL="${CODEX_APP_SERVER_README_URL:-https://raw.githubusercontent.com/openai/codex/refs/heads/main/codex-rs/app-server/README.md}"
TARGET_FILE="${SKILL_DIR}/references/openai-codex-app-server-readme-reference.md"

tmp_file="$(mktemp "${TMPDIR:-/tmp}/codex-app-server-readme.XXXXXX")"
cleanup() {
  rm -f "${tmp_file}"
}
trap cleanup EXIT

curl -fsSL "${SOURCE_URL}" -o "${tmp_file}"

if [[ ! -s "${tmp_file}" ]]; then
  echo "Fetched snapshot is empty: ${SOURCE_URL}" >&2
  exit 1
fi

mkdir -p "$(dirname "${TARGET_FILE}")"

if [[ -f "${TARGET_FILE}" ]] && cmp -s "${tmp_file}" "${TARGET_FILE}"; then
  echo "Snapshot unchanged: ${TARGET_FILE}"
  exit 0
fi

mv "${tmp_file}" "${TARGET_FILE}"
trap - EXIT

echo "Snapshot updated: ${TARGET_FILE}"
