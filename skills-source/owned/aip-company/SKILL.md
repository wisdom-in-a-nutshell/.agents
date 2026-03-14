---
name: aip-company
description: "Canonical company knowledge for AI Podcasting (AIP): positioning, business details, messaging, target customer, proof points, and company facts. Use when working on AIP strategy, website copy, messaging, pitches, founder/company descriptions, case-study framing, pricing context, or any task that needs the authoritative company understanding across `adi`, `aipodcasting-public-website`, and `blog-personal`."
---

# AIP Company

Use this skill as the canonical source of truth for AI Podcasting company context.

## What this skill is for

Use this skill when you need to understand or write about:

- what AIP is
- who it serves
- how it is positioned
- business model and pricing context
- target customer and alternatives
- traction/proof points
- founder/company facts used in company-facing work

This skill is the canonical company home. Do not create new canonical AIP company descriptions in random repos.

## Canonical references

Read only the file(s) needed for the task:

- `references/company-profile.md`
  - use for positioning, messaging, website copy, pitches, one-liners, category framing
- `references/business-details.md`
  - use for operational/business facts, pricing context, TAM, team/company details
- `references/positioning-notes.md`
  - use for older but still useful positioning reasoning and category nuance

## Routing rule

- If the task is about Adi's personal relationship to AIP, risk, identity, or current life/company tension, use `adi/memory/domains/company/AGENTS.md`.
- If the task is about AIP as a company, use this skill.
- If canonical company truth changes, update this skill first, then update downstream repo copy only where needed.

## Writing guardrails

Prefer:

- podcast operations partner
- production engine
- record and relax
- end-to-end workflow
- quality plus speed
- adapts to the client's workflow

Avoid:

- generic SaaS-editing-tool framing
- pure agency-labor framing
- vague AI claims without operational specifics

## Repo scope

This managed owned skill is routed to:

- `adi`
- `aipodcasting-public-website`
- `blog-personal`
