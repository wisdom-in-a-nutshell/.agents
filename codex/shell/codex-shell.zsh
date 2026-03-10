# Codex + Ghostty shell integration.
# Source this from a shared ~/.zshrc rather than replacing the whole shell config.

# Ensure Ghostty shell integration is active even in shells started via wrappers.
if [[ -n $GHOSTTY_RESOURCES_DIR ]]; then
  source "$GHOSTTY_RESOURCES_DIR"/shell-integration/zsh/ghostty-integration
fi

# Pick a directory, cd there, and launch Codex.
# Intended to be triggered by a Ghostty keybind via:
#   text:\x15\x03
codex_jump() {
  emulate -L zsh
  setopt local_options pipefail no_aliases

  local -a candidates
  local -a uniq
  local selected
  local dir
  local line
  local dirs_file="${CODEX_JUMP_DIRS_FILE:-$HOME/.agents/codex/shell/codex-jump-dirs.txt}"
  local usage_file="${CODEX_JUMP_USAGE_FILE:-$HOME/.local/state/codex-jump-usage.tsv}"
  local smart_sort="${CODEX_JUMP_SMART_SORT:-1}"
  local usage_tmp
  local rank_tmp
  local idx
  local now
  local count
  local last
  typeset -A usage_count
  typeset -A usage_last

  candidates=()

  if [[ -f "$dirs_file" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line#"${line%%[![:space:]]*}"}"
      line="${line%"${line##*[![:space:]]}"}"
      [[ -z "$line" || "$line" == \#* ]] && continue
      line="${line//\$HOME/$HOME}"
      if [[ "$line" == "~"* ]]; then
        line="$HOME${line#\~}"
      fi
      [[ -d "$line" ]] && candidates+=("$line")
    done < "$dirs_file"
    candidates+=("$PWD")
  else
    candidates+=(
      "$PWD"
      "$HOME/GitHub"
      "$HOME/GitHub/scripts"
      "$HOME/GitHub/win"
      "$HOME/.agents"
      "$HOME/.codex"
    )

    if [[ -d "$HOME/GitHub" ]]; then
      while IFS= read -r dir; do
        [[ -n "$dir" ]] && candidates+=("$dir")
      done < <(find "$HOME/GitHub" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
    fi
  fi

  while IFS= read -r dir; do
    uniq+=("$dir")
  done < <(printf '%s\n' "${candidates[@]}" | awk 'NF && !seen[$0]++')

  if [[ "$smart_sort" == "1" ]] && [[ -f "$usage_file" ]]; then
    while IFS=$'\t' read -r dir count last || [[ -n "${dir:-}" ]]; do
      [[ -n "${dir:-}" ]] || continue
      usage_count["$dir"]="${count:-0}"
      usage_last["$dir"]="${last:-0}"
    done < "$usage_file"

    rank_tmp="$(mktemp -t codex-jump-rank)"
    idx=0
    for dir in "${uniq[@]}"; do
      (( idx++ ))
      printf '%s\t%s\t%s\t%s\n' \
        "${usage_count[$dir]:-0}" \
        "${usage_last[$dir]:-0}" \
        "$idx" \
        "$dir" >> "$rank_tmp"
    done

    uniq=()
    while IFS=$'\t' read -r count last idx dir; do
      [[ -n "${dir:-}" ]] && uniq+=("$dir")
    done < <(sort -t $'\t' -k1,1nr -k2,2nr -k3,3n "$rank_tmp")
    rm -f "$rank_tmp"
  fi

  if command -v fzf >/dev/null 2>&1; then
    selected="$(
      printf '%s\n' "${uniq[@]}" \
        | fzf --prompt='Codex Dir > ' --height=45% --layout=reverse --cycle --border
    )" || return 0
  else
    local i=1

    if (( ${#uniq[@]} == 0 )); then
      echo "No directories available for codex_jump."
      return 1
    fi

    echo "Select directory:"
    for dir in "${uniq[@]}"; do
      echo "  $i) $dir"
      (( i++ ))
    done
    echo -n "> "
    read -r i
    [[ "$i" =~ ^[0-9]+$ ]] || return 0
    (( i >= 1 && i <= ${#uniq[@]} )) || return 0
    selected="${uniq[$i]}"
  fi

  [[ -n "${selected:-}" ]] || return 0

  if [[ "$smart_sort" == "1" ]]; then
    mkdir -p "$(dirname "$usage_file")"
    now="$(date +%s)"

    if [[ -f "$usage_file" ]]; then
      while IFS=$'\t' read -r dir count last || [[ -n "${dir:-}" ]]; do
        [[ -n "${dir:-}" ]] || continue
        usage_count["$dir"]="${count:-0}"
        usage_last["$dir"]="${last:-0}"
      done < "$usage_file"
    fi

    count="${usage_count[$selected]:-0}"
    usage_count["$selected"]="$((count + 1))"
    usage_last["$selected"]="$now"

    usage_tmp="$(mktemp -t codex-jump-usage)"
    for dir in "${(k)usage_count}"; do
      printf '%s\t%s\t%s\n' "$dir" "${usage_count[$dir]}" "${usage_last[$dir]:-0}" >> "$usage_tmp"
    done
    sort -t $'\t' -k2,2nr -k3,3nr "$usage_tmp" > "${usage_tmp}.sorted"
    mv "${usage_tmp}.sorted" "$usage_file"
    rm -f "$usage_tmp"
  fi

  cd "$selected" || return 1

  if command -v codex >/dev/null 2>&1; then
    command codex
  else
    echo "codex is not installed or not on PATH."
    return 1
  fi
}

alias cj='codex_jump'

# Launch Codex and, when interrupted from Ghostty, route to codex_jump.
_codex_autostart_loop() {
  command -v codex >/dev/null 2>&1 || return 0

  command codex
  local ec=$?

  if [[ ( $ec -eq 130 || $ec -eq 0 ) ]] && [[ -n "${GHOSTTY_RESOURCES_DIR:-}" ]] && [[ "${CODEX_DISABLE_INTERRUPT_PICKER:-0}" != "1" ]]; then
    codex_jump
    return 0
  fi

  return "$ec"
}

# Auto-start Codex for interactive Ghostty shells (new tabs/splits/windows).
# Disable for a shell session with: export CODEX_DISABLE_AUTOSTART=1
if [[ -o interactive ]] && [[ -n "${GHOSTTY_RESOURCES_DIR:-}" ]]; then
  # Ensure cwd reporting is active before Codex autostarts so new tabs/splits
  # inherit the currently focused directory instead of a stale fallback cwd.
  if (( $+functions[_ghostty_deferred_init] )); then
    _ghostty_deferred_init >/dev/null 2>&1 || true
  fi

  if [[ "${CODEX_AUTOSTART_SKIP_ONCE:-0}" == "1" ]]; then
    unset CODEX_AUTOSTART_SKIP_ONCE
  elif [[ "${CODEX_DISABLE_AUTOSTART:-0}" != "1" ]] && command -v codex >/dev/null 2>&1; then
    _codex_autostart_loop
  fi
fi
