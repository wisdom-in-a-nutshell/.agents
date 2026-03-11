---
name: architecture-docs
description: Write or refactor high-level architecture documentation for humans. Use when Codex needs to explain how a system works, how major parts connect, how data or requests flow through the system, or how boundaries and responsibilities are divided. Prefer this skill for `docs/architecture/*`, visual-first system overviews, Mermaid diagrams, and repo docs work where the user wants something easy to scan and understand quickly.
---

# Architecture Docs

Write architecture docs for humans first.

Use this skill to produce docs that help a person quickly understand:

- what the main parts of the system are
- how they connect
- how requests, jobs, or data move through the system
- where important boundaries and responsibilities sit

Keep architecture docs visual-first and simple.

## Core rules

- Put canonical architecture docs in `docs/architecture/` unless the repo has an explicit local exception.
- Write for fast human understanding, not exhaustive implementation detail.
- Start with a short plain-English explanation.
- Prefer a simple Mermaid `flowchart TD` diagram near the top.
- Keep diagrams high-level and readable.
- Prefer progressive disclosure when one diagram would mix too many levels or concerns.
  Start with the simplest useful overview, then add Level 2 / Level 3 zoom-ins instead of forcing one dense figure.
- Push exact field names, env vars, limits, commands, schemas, and operational contracts into `docs/references/`.
- If repo-local docs guidance conflicts with this skill, follow the repo-local docs contract.

## Workflow

1. Read the repo-local docs contract first.
   In particular: root `AGENTS.md`, `docs/AGENTS.md`, and the relevant existing `docs/architecture/*` pages.

2. Decide whether the requested doc is really architecture.
   If it is mainly about system shape, boundaries, flow, or major tradeoffs, keep it in `docs/architecture/`.
   If it is mainly about exact facts or lookup rules, put it in `docs/references/` instead.
   Read `references/02-architecture-vs-references.md` when unsure.

3. Collect only the minimum context needed to explain the system.
   Focus on major components, boundaries, and flows.
   Avoid dumping low-level implementation details into the architecture doc.

4. Draft the doc in this order:
   - short plain-English overview
   - Mermaid `flowchart TD`
   - short section explaining the main flow or boundaries
   - short notes on tradeoffs or important constraints if needed
   - for broader systems, use a Level 1 / Level 2 / Level 3 structure so each diagram explains one idea

5. Keep the diagram simple.
   Use a few meaningful nodes and connections, not every internal detail.
   Keep container labels passive: arrows should connect real components, not the block titles.
   Use consistent zone coloring only when it materially improves scanability.
   Read `references/01-mermaid-guidelines.md` before writing or refactoring diagrams.

6. Keep the document easy to skim.
   Use short sections, direct wording, and minimal jargon.
   If the target renderer is available (for example Obsidian), verify the actual render and refine from what a human will really see.

7. If exact facts are needed, create or update a companion doc in `docs/references/` and link it.

## Default doc shape

Use this default structure unless the repo already has a strong local pattern:

1. Title
2. 2-4 sentence overview in plain English
3. Mermaid `flowchart TD`
4. Main parts / boundaries
5. Main flow
6. Key tradeoffs or notes
7. Links to deeper references if needed

Read `references/00-doc-shape.md` for the fuller template.

## When to keep it high-level

Architecture docs should answer:

- "What are the main parts?"
- "How do they connect?"
- "Where does this responsibility live?"
- "How does the system basically work?"

Architecture docs should usually not answer:

- every field name
- every API parameter
- exact env var lists
- every cache key or schema detail
- step-by-step operational runbooks

Those belong in `docs/references/`.

## Related skills

- Use `$pretty-mermaid` if you need to render, theme, or iterate on Mermaid output more deeply.
- Use `$agent-native-repo-playbook` when the user is deciding the repo-wide docs contract or AGENTS/docs policy.
