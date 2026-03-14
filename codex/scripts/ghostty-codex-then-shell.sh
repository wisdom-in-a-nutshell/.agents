#!/bin/zsh
set -euo pipefail

_codex_last_dir_file() {
  printf '%s' "${CODEX_LAST_DIR_FILE:-$HOME/.local/state/codex-control-plane/ghostty-last-dir.txt}"
}

_codex_restore_last_dir() {
  local state_file saved_dir

  [[ "${CODEX_RESTORE_LAST_DIR:-1}" == "1" ]] || return 0
  [[ "$PWD" == "$HOME" ]] || return 0

  state_file="$(_codex_last_dir_file)"
  [[ -f "$state_file" ]] || return 0

  IFS= read -r saved_dir < "$state_file" || return 0
  [[ -n "$saved_dir" && -d "$saved_dir" ]] || return 0

  cd "$saved_dir"
}

_codex_report_pwd() {
  printf '\033]7;kitty-shell-cwd://%s%s\007' "${HOST:-$HOSTNAME}" "$PWD"
}

_codex_set_surface_title() {
  local title="${PWD:t}"
  [[ -n "$title" ]] || title="$PWD"
  printf '\033]1;%s\007' "$title"
  printf '\033]2;%s\007' "$title"
}

# Start Codex when invoked as a Ghostty startup entrypoint (typically `initial-command`).
# When Codex exits, keep the terminal open by falling back to an interactive login shell.
if command -v codex >/dev/null 2>&1; then
  _codex_restore_last_dir
  _codex_report_pwd
  _codex_set_surface_title
  codex
fi

# If ~/.zshrc auto-starts Codex for Ghostty shells, skip that once here so
# exiting this initial Codex session lands in a shell instead of relaunching.
export CODEX_AUTOSTART_SKIP_ONCE=1
exec /bin/zsh -l
