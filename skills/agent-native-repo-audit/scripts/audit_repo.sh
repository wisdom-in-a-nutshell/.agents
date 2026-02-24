#!/usr/bin/env bash
set -euo pipefail

repo="${1:-$PWD}"

if [ ! -d "$repo" ]; then
  echo "ERROR: repo path does not exist: $repo" >&2
  exit 1
fi

if [ ! -d "$repo/.git" ]; then
  echo "ERROR: target is not a git repo: $repo" >&2
  exit 1
fi

# 1) Root AGENTS
root_agents=0
[ -f "$repo/AGENTS.md" ] && root_agents=1

# 2) Scoped AGENTS (excluding root)
scoped_agents=0
if command -v find >/dev/null 2>&1; then
  scoped_agents=$(find "$repo" -name AGENTS.md -not -path '*/.git/*' -not -path '*/node_modules/*' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$scoped_agents" -gt 0 ] && [ "$root_agents" -eq 1 ]; then
    scoped_agents=$((scoped_agents - 1))
  fi
fi

# 3) docs/
docs_present=0
[ -d "$repo/docs" ] && docs_present=1

# 4) docs/projects/*/tasks.md
plans_count=0
if [ -d "$repo/docs/projects" ]; then
  plans_count=$(find "$repo/docs/projects" -name tasks.md 2>/dev/null | wc -l | tr -d ' ')
fi

# 5) workflows
workflows_count=0
if [ -d "$repo/.github/workflows" ]; then
  workflows_count=$(find "$repo/.github/workflows" -type f 2>/dev/null | wc -l | tr -d ' ')
fi

# 6) CI quality refs
quality_refs=0
if [ -d "$repo/.github/workflows" ]; then
  quality_refs=$(rg -n "(pytest|jest|vitest|playwright|go test|cargo test|npm run test|pnpm test|uv run pytest|eslint|ruff|flake8|mypy|typecheck|lint|tsc|basedpyright|black --check|prettier --check)" "$repo/.github/workflows" 2>/dev/null | wc -l | tr -d ' ')
fi

# 7) Local guardrail config
guardrail_files=0
[ -f "$repo/package.json" ] && guardrail_files=$((guardrail_files + 1))
[ -f "$repo/pyproject.toml" ] && guardrail_files=$((guardrail_files + 1))
[ -f "$repo/.pre-commit-config.yaml" ] && guardrail_files=$((guardrail_files + 1))
[ -f "$repo/ruff.toml" ] && guardrail_files=$((guardrail_files + 1))
[ -f "$repo/eslint.config.js" ] && guardrail_files=$((guardrail_files + 1))
[ -f "$repo/.eslintrc" ] && guardrail_files=$((guardrail_files + 1))
[ -f "$repo/.eslintrc.js" ] && guardrail_files=$((guardrail_files + 1))

# 8) Local skills
skills_count=0
if [ -d "$repo/.agents/skills" ]; then
  skills_count=$(find "$repo/.agents/skills" -maxdepth 2 -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')
fi

score=0
[ "$root_agents" -eq 1 ] && score=$((score + 15))
[ "$scoped_agents" -gt 0 ] && score=$((score + 10))
[ "$docs_present" -eq 1 ] && score=$((score + 10))
[ "$plans_count" -gt 0 ] && score=$((score + 15))
[ "$workflows_count" -gt 0 ] && score=$((score + 10))
[ "$quality_refs" -gt 0 ] && score=$((score + 20))
[ "$guardrail_files" -gt 0 ] && score=$((score + 10))
[ "$skills_count" -gt 0 ] && score=$((score + 10))

bucket="Not ready"
if [ "$score" -ge 85 ]; then
  bucket="Strong"
elif [ "$score" -ge 65 ]; then
  bucket="Functional but uneven"
elif [ "$score" -ge 40 ]; then
  bucket="Needs scaffolding"
fi

printf '%s\n' "# Agent-Native Repo Audit"
printf '%s\n' "- Repo: $repo"
printf '%s\n' "- Score: $score/100 ($bucket)"
printf '%s\n' ""
printf '%s\n' "## Signals"
printf '%s\n' "- Root AGENTS.md: $root_agents"
printf '%s\n' "- Scoped AGENTS.md count (excluding root): $scoped_agents"
printf '%s\n' "- docs/ present: $docs_present"
printf '%s\n' "- tasks.md plan count: $plans_count"
printf '%s\n' "- workflow file count: $workflows_count"
printf '%s\n' "- CI quality references: $quality_refs"
printf '%s\n' "- guardrail config files: $guardrail_files"
printf '%s\n' "- local skill count: $skills_count"

printf "\n## Priority Gaps\n"

any_gap=0
if [ "$root_agents" -eq 0 ]; then
  printf "1. Missing root AGENTS.md map.\n"
  any_gap=1
fi
if [ "$docs_present" -eq 0 ]; then
  printf "1. Missing docs/ system-of-record directory.\n"
  any_gap=1
fi
if [ "$plans_count" -eq 0 ]; then
  printf "1. Missing docs/projects/*/tasks.md resumable plan artifact.\n"
  any_gap=1
fi
if [ "$quality_refs" -eq 0 ]; then
  printf "1. No test/lint/typecheck references in workflows.\n"
  any_gap=1
fi
if [ "$skills_count" -eq 0 ]; then
  printf "1. No repo-local skills for repeatable workflows.\n"
  any_gap=1
fi
if [ "$any_gap" -eq 0 ]; then
  printf "1. No high-priority structural gaps found by baseline rubric.\n"
fi
