---
name: agent-native-repo-playbook
description: Provide agent-native repository best-practice recommendations for a solo developer workflow where humans provide intent and agents write 100% of code. Use when asked how to improve AGENTS/docs/guardrails, reduce agent drift, improve autonomous execution loops, or align a repo to OpenAI harness-engineering style practices without overcomplicating process.
---

# Agent Native Repo Playbook

## Overview
Use this playbook to recommend practical improvements for agent-first software development.

Operating model:
- Solo developer sets intent and priorities.
- Agents always write 100% of code and maintain docs.
- Repository structure is optimized for agent legibility and repeatability.

## Workflow
1. Read the repo's current guidance and structure:
   - `AGENTS.md` files
   - `docs/` organization
   - `.github/workflows/`
   - local `.agents/skills/`
2. Compare current state against:
   - `references/best-practices.md`
   - `references/agents-md-best-practices.md`
   - `references/docs-structure-and-maintenance.md`
   - When recommending or writing any `AGENTS.md` content, apply `references/agents-md-best-practices.md` as the AGENTS-specific quality standard.
3. Produce recommendations in three tiers:
   - Immediate (high leverage, low effort)
   - Near-term (high leverage, medium effort)
   - Later (structural improvements)
4. Keep output recommendation-first. Do not implement unless user asks.

## Output Format
1. `What is working`: short bullets.
2. `Highest-leverage gaps`: short bullets.
3. `AGENTS audit`: `Keep / Move / Delete` decisions for major `AGENTS.md` lines or sections.
4. `Recommended next moves`:
   - Immediate
   - Near-term
   - Later
5. `Evidence`: include concrete file paths for each major gap/recommendation.

## Rules
- Prefer recommendations that reduce human coordination load.
- Prefer mechanical guardrails over prose-only guidance.
- Preserve the operating principle: humans set intent; agents write 100% of code.
- Keep AGENTS concise; move detailed guidance into docs.
- Keep root `AGENTS.md` as a router; use nested `AGENTS.md` only where local boundary rules materially differ.
- When editing or proposing `AGENTS.md`, follow `references/agents-md-best-practices.md` and include an AGENTS audit (`Keep / Move / Delete`).
- When defining docs contracts, prefer:
  - `docs/architecture/` as human-first and visual-first (Mermaid in Markdown + short helper text),
  - `docs/references/` as durable implementation facts, command snippets, and operational lookup material for agents.
- Prioritize feedback loops that agents can run autonomously.
- Avoid heavy process designed for large teams unless explicitly requested.
- Recommend one docs contract across repos unless the user requests exceptions.
- Use `$project-planner` for creating/updating `docs/projects/<project>/tasks.md`.
- Use `$project-executor` for execution against those tasks files.
- If repo-local guidance conflicts with this playbook, prefer repo-local sources of truth (`AGENTS.md`, decision docs, and architecture docs).

## Resources
- `references/best-practices.md`: baseline best practices for this workflow.
- `references/agents-md-best-practices.md`: AGENTS quality gate, nested AGENTS decision rules, and keep/move/delete audit checklist.
- `references/docs-structure-and-maintenance.md`: baseline docs layout and update rules.
