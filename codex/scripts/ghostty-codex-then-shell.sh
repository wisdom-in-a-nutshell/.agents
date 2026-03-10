#!/bin/zsh
set -euo pipefail

# Start Codex when invoked as a Ghostty startup entrypoint (typically `initial-command`).
# When Codex exits, keep the terminal open by falling back to an interactive login shell.
if command -v codex >/dev/null 2>&1; then
  codex
fi

# If ~/.zshrc auto-starts Codex for Ghostty shells, skip that once here so
# exiting this initial Codex session lands in a shell instead of relaunching.
export CODEX_AUTOSTART_SKIP_ONCE=1
exec /bin/zsh -l
