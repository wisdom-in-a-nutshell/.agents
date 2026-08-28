#!/usr/bin/env bash

capture_local_production_source() {
  local repo_root="$1"
  local required_branch="$2"
  local observed_branch observed_sha observed_status

  observed_branch="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
  observed_sha="$(git -C "$repo_root" rev-parse --verify 'HEAD^{commit}' 2>/dev/null || true)"
  observed_status="$(git -C "$repo_root" status --porcelain --untracked-files=all 2>/dev/null || true)"
  if [[ "$observed_branch" != "$required_branch" || -z "$observed_sha" || -n "$observed_status" ]]; then
    return 1
  fi
  LOCAL_PRODUCTION_SOURCE_BRANCH="$observed_branch"
  LOCAL_PRODUCTION_SOURCE_SHA="$observed_sha"
}

verify_local_production_source() {
  local repo_root="$1"
  local expected_branch="$2"
  local expected_sha="$3"
  local observed_branch observed_sha observed_status

  observed_branch="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
  observed_sha="$(git -C "$repo_root" rev-parse --verify 'HEAD^{commit}' 2>/dev/null || true)"
  observed_status="$(git -C "$repo_root" status --porcelain --untracked-files=all 2>/dev/null || true)"
  [[ "$observed_branch" == "$expected_branch" ]] || return 1
  [[ "$observed_sha" == "$expected_sha" ]] || return 1
  [[ -z "$observed_status" ]] || return 1
}
