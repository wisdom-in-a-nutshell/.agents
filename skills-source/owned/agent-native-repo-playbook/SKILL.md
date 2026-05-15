---
name: agent-native-repo-playbook
description: Provide agent-native repository best-practice recommendations and autonomous execution guidance for a solo developer workflow where humans provide intent and agents write 100% of code. Use when asked how to improve AGENTS/docs/guardrails, reduce agent drift, improve autonomous execution loops or automations, avoid waiting for human feedback in agent loops, or align a repo to OpenAI harness-engineering style practices without overcomplicating process.
---

# Agent Native Repo Playbook

## Overview
Use this playbook to recommend practical improvements for agent-first software development.

Operating model:
- Solo developer sets intent and priorities.
- Agents always write 100% of code and maintain docs.
- Repository structure is optimized for agent legibility and repeatability.
- In automation, heartbeat, or active-goal contexts, agents should assume the
  human has delegated execution. Do not wait for feedback unless truly blocked;
  make the best conservative decision, implement it, validate it, document
  durable behavior, and report what changed.

## Workflow
1. Read the repo's current guidance and structure:
   - `AGENTS.md` files
   - `STRUCTURE.md` or other repo-specific structure maps when present
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
4. Keep output recommendation-first for advisory requests. Implement directly
   when the user asks, when automation/goal instructions authorize execution,
   or when the request is explicitly to make the repo more autonomous.
5. In automation mode, prefer one useful validated change over asking for
   permission. Ask only when the next step is destructive, irreversible,
   requires a missing secret/account decision, or conflicts with repo-local
   guidance.

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
- For autonomous loops, bias toward action: inspect, decide, edit, validate,
  document, and summarize. Do not pause for human approval just because several
  reasonable implementation choices exist; choose the smallest reversible
  option that matches repo guidance.
- Keep root guidance concise; move durable detail into the repo's chosen canonical layer.
- For normal software repos, keep root `AGENTS.md` as a router and use nested `AGENTS.md` only where local boundary rules materially differ. If a repo intentionally rejects `AGENTS.md` and uses another passive/bootstrapped map such as `STRUCTURE.md`, honor that design.
- When editing or proposing `AGENTS.md`, follow `references/agents-md-best-practices.md`; when the repo uses `STRUCTURE.md` or equivalent, audit that root guidance instead.
- When defining docs contracts, prefer:
  - `docs/architecture/` as quick human-overview and visual-first (Mermaid in Markdown + short helper text),
  - `docs/references/` as durable implementation facts, command snippets, and operational lookup material for humans and agents.
- Prefer plain-English wording over complex prose for architecture-facing docs so a solo human can scan and understand quickly.
- Keep docs policy lightweight: if a repo has local docs placement guidance, use it. Otherwise default to `docs/architecture/` for system shape and `docs/references/` for exact facts.
- Do not introduce centralized policy layers or audit scripts unless the user explicitly asks.
- Prioritize feedback loops that agents can run autonomously.
- Avoid heavy process designed for large teams unless explicitly requested.
- Recommend one docs contract across repos unless the user requests exceptions.
- Use `$project` for creating, resuming, replanning, and closing project trackers in the repo's tracker home.
- If repo-local guidance conflicts with this playbook, prefer repo-local sources of truth (`STRUCTURE.md`, `AGENTS.md`, decision docs, and architecture docs).

## Resources
- `references/best-practices.md`: baseline best practices for this workflow.
- `references/agents-md-best-practices.md`: AGENTS quality gate, nested AGENTS decision rules, and keep/move/delete audit checklist.
- `references/docs-structure-and-maintenance.md`: baseline docs layout and update rules.
