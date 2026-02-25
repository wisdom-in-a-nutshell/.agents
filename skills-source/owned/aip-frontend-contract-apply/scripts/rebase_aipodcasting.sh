#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${REPO_PATH:-$HOME/GitHub/aipodcasting}"

if [ ! -d "$REPO_PATH/.git" ]; then
  echo "Expected git repo at $REPO_PATH" >&2
  exit 1
fi

cd "$REPO_PATH"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "Expected branch 'main' but found '$BRANCH'." >&2
  exit 1
fi

if [ -d ".git/rebase-apply" ] || [ -d ".git/rebase-merge" ]; then
  echo "Rebase already in progress. Resolve it before running this script." >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "chore: sync aipodcasting changes"
fi

git fetch origin

git rebase origin/main

git push origin main
