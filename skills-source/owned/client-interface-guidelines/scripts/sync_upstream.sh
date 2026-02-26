#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
refs_dir="$skill_dir/references"
repo_url="https://github.com/cli-guidelines/cli-guidelines.git"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

git clone --depth 1 "$repo_url" "$tmp_dir/repo"
repo="$tmp_dir/repo"

cp "$repo/content/_index.md" "$refs_dir/command-line-interface-guidelines.md"
cp "$repo/README.md" "$refs_dir/upstream-readme.md"
cp "$repo/LICENSE" "$refs_dir/upstream-license-cc-by-sa-4.0.md"

{
  printf '# CLI Guidelines Rule Index\n\n'
  printf 'Generated from: content/_index.md in https://github.com/cli-guidelines/cli-guidelines\n\n'
  printf '## Top-Level Sections\n'
  awk '/^## /{line=$0; sub(/ \{#.*\}/,"",line); print "- " line}' "$repo/content/_index.md"
  printf '\n## Actionable Rules (Bolded)\n'
  awk '/^\*\*/{print "- " $0}' "$repo/content/_index.md"
} > "$refs_dir/rule-index.md"

commit_hash="$(git -C "$repo" rev-parse HEAD)"
snapshot_date="$(date '+%Y-%m-%d')"

cat > "$refs_dir/source-snapshot.md" <<SNAP
# Source Snapshot

- Upstream repository: https://github.com/cli-guidelines/cli-guidelines
- Snapshot date: $snapshot_date
- Upstream commit: $commit_hash
- Primary source file: content/_index.md
- License: CC BY-SA 4.0

## Refresh Command

- Run bash scripts/sync_upstream.sh from this skill directory.
SNAP

echo "Refreshed client-interface-guidelines references from $repo_url @ $commit_hash"
