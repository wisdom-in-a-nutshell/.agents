---
name: agent-native-repo-playbook
description: Audit and improve repositories for a solo developer, high-permission, agent-native workflow where humans set intent and improve the harness while agents write code, docs, tests, tooling, and checks. Use for repo harness audits, readiness scores, AGENTS/docs/guardrail reviews, proof-of-work expectations, YOLO/direct-to-main workflow design, reducing agent drift, improving autonomous execution loops, or aligning repos to OpenAI harness-engineering practices without adding team-heavy process.
---

# Agent Native Repo Playbook

## Overview
Use this playbook to recommend practical improvements for agent-first software development.

Operating model:
- Solo developer sets intent and priorities.
- Agents always write 100% of code and maintain docs.
- Repository structure is optimized for agent legibility and repeatability.

## Modes
- Default audit: produce recommendation-first guidance.
- Scorecard audit: when the user asks for score, rubric, readiness, maturity, or benchmark, load `references/harness-readiness-rubric.md`.
- AGENTS audit: when reviewing root or nested guidance, load `references/agents-md-best-practices.md`.
- Docs audit: when reviewing docs placement or freshness, load `references/docs-structure-and-maintenance.md`.
- Source trace: use `references/ryan-harness-principles.md`; load raw Ryan sources only when exact source lookup is requested.

## Workflow
1. Read the repo's current guidance and structure:
   - `AGENTS.md` files
   - `STRUCTURE.md` or other repo-specific structure maps when present
   - `docs/` organization
   - `.github/workflows/`
   - local `.agents/skills/`
2. Compare current state against:
   - `references/best-practices.md`
   - `references/harness-readiness-rubric.md` when scoring or benchmarking
   - `references/ryan-harness-principles.md` when applying OpenAI harness-engineering patterns
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
3. Guidance audit: `Keep / Move / Delete` decisions for major root guidance lines or sections (`AGENTS.md`, `STRUCTURE.md`, or equivalent).
4. `Recommended next moves`:
   - Immediate
   - Near-term
   - Later
5. `Evidence`: include concrete file paths for each major gap/recommendation.

## Rules
- Prefer recommendations that reduce human coordination load.
- Prefer mechanical guardrails over prose-only guidance.
- Preserve the operating principle: humans set intent; agents write 100% of code.
- Keep root guidance concise; move durable detail into the repo's chosen canonical layer.
- For normal software repos, keep root `AGENTS.md` as a router and use nested `AGENTS.md` only where local boundary rules materially differ. If a repo intentionally rejects `AGENTS.md` and uses another passive/bootstrapped map such as `STRUCTURE.md`, honor that design.
- When editing or proposing `AGENTS.md`, follow `references/agents-md-best-practices.md`; when the repo uses `STRUCTURE.md` or equivalent, audit that root guidance instead.
- When defining docs contracts, prefer:
  - `docs/architecture/` as quick human-overview and visual-first (Mermaid in Markdown + short helper text),
  - `docs/references/` as durable implementation facts, command snippets, and operational lookup material for humans and agents.
- Prefer plain-English wording over complex prose for architecture-facing docs so a solo human can scan and understand quickly.
- When writing architecture docs, use the structure and Mermaid guidance in `references/docs-structure-and-maintenance.md`; keep exact contracts, schemas, env vars, and command details in `docs/references/`.
- Keep docs policy lightweight: if a repo has local docs placement guidance, use it. Otherwise default to `docs/architecture/` for system shape and `docs/references/` for exact facts.
- Do not introduce centralized policy layers or audit scripts unless the user explicitly asks.
- Prioritize feedback loops that agents can run autonomously.
- Avoid heavy process designed for large teams unless explicitly requested.
- Recommend one docs contract across repos unless the user requests exceptions.
- Use `$project` for creating, resuming, replanning, and closing project trackers in the repo's tracker home.
- If repo-local guidance conflicts with this playbook, prefer repo-local sources of truth (`STRUCTURE.md`, `AGENTS.md`, decision docs, and architecture docs).

## Resources
- `references/best-practices.md`: baseline best practices for this workflow.
- `references/harness-readiness-rubric.md`: scorecard dimensions and output shape for agent-native readiness audits.
- `references/ryan-harness-principles.md`: distilled Ryan Lopopolo / OpenAI harness-engineering principles adapted for this skill.
- `references/agents-md-best-practices.md`: AGENTS quality gate, nested AGENTS decision rules, and keep/move/delete audit checklist.
- `references/docs-structure-and-maintenance.md`: baseline docs layout and update rules.
- `references/raw/ryan-lopopolo-openai/source-manifest.md`: Ryan Lopopolo harness-engineering source inventory and raw transcript file map; use only for source lookup or future distillation work.
