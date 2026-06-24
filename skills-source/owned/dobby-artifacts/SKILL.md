---
name: dobby-artifacts
description: "Create, promote, organize, update, or dashboard-link visible Dobby workspace artifacts: self-contained working surfaces such as HTML mini dashboards, tables, trackers, planning boards, calculators, maps, timelines, reflection tools, or visual reports under workspace area artifact folders for the current Dobby person workspace while keeping shared dashboard behavior in `dobby-engine`."
---

# Dobby Artifacts

## Purpose

Use this skill when a Dobby workspace needs a visible, reusable working surface that the user and Dobby can both open, revisit, and improve.

A Dobby artifact is not just a temporary preview and not just documentation. It is a workspace-owned surface: for example an HTML worksheet, tracker, dashboard, table, calculator, map, timeline, or visual report backed by whatever local data pattern best fits the job.

## Ownership Rules

- Work from the current Dobby workspace (`~/GitHub/adi` or `~/GitHub/angie`) unless the user explicitly names another workspace.
- Keep person-private artifact content in that person's workspace.
- Put shared serving, dashboard listing, routing, or engine behavior in `~/GitHub/dobby-engine`.
- Put skill/control-plane changes in `~/GitHub/agents`.
- Do not use `~/GitHub/scripts` for artifact behavior unless the change is truly machine-local service plumbing.
- Keep the implementation workspace-agnostic. Do not hardcode Angie or Adi unless the artifact content itself is personal.

## When an Artifact Is the Right Shape

Create or promote an artifact when the work is visual, interactive, revisitable, or easier to use as a contained surface than as prose.

Do not use an artifact for:

- plain durable facts that belong in `canon.md`
- open loops or reminders that belong in Shelf
- raw journal/check-in text
- one-off scratch files that do not need to be revisited

If a temporary preview becomes useful enough to keep, promote it into the artifact container below.

## Standard Container

Before creating or changing a durable artifact container, read `references/artifact-contract.md`.

Default location:

```text
memory/areas/<area>/artifacts/<slug>/
  artifact.json
  index.html
  data/          # optional source data
  style.css      # optional
  script.js      # optional
  assets/        # optional
```

The folder is the stable boundary. Inside it, choose the simplest source/data pattern that fits the artifact.

## Source-of-Truth Choice

Choose for the user; do not make a non-technical user decide between implementation formats.

Recommended defaults:

- **JSON + HTML** for structured worksheets, trackers, tables, and dashboard-like views.
- **HTML-only** for small static explainers or polished one-page views.
- **Markdown + HTML** when prose is primary but a nicer visible surface helps.
- **CSV + HTML** only when the user will realistically maintain tabular data in CSV.
- **XLSX** only when the user needs native spreadsheet formulas, pivoting, or Excel editing. Otherwise, avoid keeping Excel as the hidden real source.

Briefly explain the choice in plain language.

## Workflow

1. Identify the workspace, area, and slug.
2. Create or update `memory/areas/<area>/artifacts/<slug>/`.
3. Decide the internal source pattern and make one clear source of truth.
4. Write or update `artifact.json`.
5. Build the visible entry file, usually `index.html`.
6. If dashboard support is missing or needs improvement, change the generic behavior in `dobby-engine`, not in the person workspace.
7. Validate every touched repo with its fast check.
8. If useful, open the local dashboard URL for the user.

## Dashboard Expectations

A Dobby dashboard may expose declared artifacts at:

```text
/artifacts/<area>/<slug>/
```

Only declared artifact folders should be served. Do not add broad static serving of arbitrary workspace files.

Pinned artifacts may appear on the dashboard home as working surfaces. Keep that behavior generic and shared in `dobby-engine`.
