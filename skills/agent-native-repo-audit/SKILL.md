---
name: agent-native-repo-audit
description: Audit any local repository for solo-developer, agent-native readiness where agents write 100% of code and humans provide intent. Use when asked to assess whether a repo is "good or bad" for agent-first execution, identify top gaps, compare repos with one consistent rubric, or propose prioritized improvements without implementing them.
---

# Agent Native Repo Audit

## Overview
Run one consistent readiness audit for any repo. Keep it simple: one workflow, one baseline, one scoring model.

This skill assumes:
- Solo developer workflow.
- Human provides intent.
- Agents write and maintain all code and docs.

## Workflow
1. Resolve target repo path from user input. If none is provided, use current directory.
2. Run `scripts/audit_repo.sh <repo-path>`.
3. Read the generated report and summarize in plain language:
   - Overall readiness score
   - Strongest signals
   - Highest-leverage gaps
   - Top 3 next fixes
4. Stay in audit mode by default. Do not edit files unless user explicitly asks.

## Output Format
Use this structure in responses:
1. `Score`: `X/100` with a one-line interpretation.
2. `What is working`: short bullets.
3. `Gaps`: ordered by impact.
4. `Next 3 fixes`: concrete and minimal.

## Rules
- Apply the same rubric every time; do not invent repo-specific scoring rules.
- Do not branch by repo type. Use one universal baseline.
- Favor mechanical enforceability over prose-only guidance.
- Call out missing agent legibility (docs, plans, guardrails, repeatable commands).
- Keep recommendations small, automatable, and easy for agents to execute.

## Resources
- `scripts/audit_repo.sh`: deterministic repo audit and scoring.
- `references/checklist.md`: rubric details used by the script.
