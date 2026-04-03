#!/usr/bin/env bash
set -euo pipefail

APPLY=0
PYTHON_BIN="${PYTHON_BIN:-python3}"
BREW_BIN="${BREW_BIN:-$(command -v brew || true)}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Ensure machine dependencies required by the managed global pdf skill.

Default mode is dry-run. Use --apply to install missing dependencies.

Options:
  --apply            Install missing dependencies
  --dry-run          Show actions only (default)
  --python <path>    Override python3 used for import checks and pip install
  --brew <path>      Override brew path used to install poppler
  -h, --help         Show this help
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

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
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --brew)
      BREW_BIN="${2:-}"
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

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python not found: $PYTHON_BIN"

if command -v pdftoppm >/dev/null 2>&1; then
  log "OK: pdftoppm already available"
else
  [[ -n "$BREW_BIN" ]] || die "pdftoppm missing and Homebrew not found. Install poppler first."
  if (( APPLY == 1 )); then
    log "+ $BREW_BIN install poppler"
    "$BREW_BIN" install poppler
  else
    log "WOULD INSTALL: poppler via $BREW_BIN install poppler"
  fi
fi

missing_modules="$("$PYTHON_BIN" - <<'PY'
mods = ["reportlab", "pdfplumber", "pypdf"]
missing = []
for name in mods:
    try:
        __import__(name)
    except Exception:
        missing.append(name)
print(" ".join(missing))
PY
)"

if [[ -z "$missing_modules" ]]; then
  log "OK: Python PDF modules already available"
else
  if (( APPLY == 1 )); then
    log "+ $PYTHON_BIN -m pip install --user --break-system-packages reportlab pdfplumber pypdf"
    "$PYTHON_BIN" -m pip install --user --break-system-packages reportlab pdfplumber pypdf
    "$PYTHON_BIN" - <<'PY'
for name in ("reportlab", "pdfplumber", "pypdf"):
    __import__(name)
print("OK: Python PDF modules installed")
PY
  else
    log "WOULD INSTALL: Python PDF modules via $PYTHON_BIN -m pip install --user --break-system-packages reportlab pdfplumber pypdf"
  fi
fi
