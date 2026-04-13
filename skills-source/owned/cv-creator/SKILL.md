---
name: cv-creator
description: Generate, update, tailor, compile, and visually review a repo-local LaTeX CV/resume and cover letter. Use when the user wants to create or improve a CV, tailor a resume for a role or company, compile LaTeX CV files to PDF, review formatting, or set up a clean `reference/career/` structure with `cv/latex/base/` and `cv/latex/tailored/`.
---

# CV Creator

Use this skill for repo-local career materials. Keep the workflow shared, but keep the person's actual career facts inside the current repo.

## Repo contract

Expect this layout unless the repo clearly documents a different one:

- `reference/career/README.md`
- `reference/career/profile.md`
- `reference/career/tailoring-guide.md`
- `reference/career/job-tracker/`
- `reference/career/cv/latex/.gitignore`
- `reference/career/cv/latex/base/resume.tex`
- `reference/career/cv/latex/base/cover-letter.tex`
- `reference/career/cv/latex/tailored/<company>/job-description.md`
- `reference/career/cv/latex/tailored/<company>/resume.tex`
- `reference/career/cv/latex/tailored/<company>/cover-letter.tex`

If the contract is missing, create the minimal structure first instead of improvising files in random places.

Read `references/structure-contract.md` when you need the exact folder expectations or migration pattern.

Read `references/template-patterns.md` when you need to understand or modify the LaTeX template's structure, preamble, custom commands (`\role`, `\labelrow`, `\sep`), spacing system, or section conventions. This is the canonical reference for "how does a base resume look in this skill" and "how do I add a new section without breaking the rhythm."

## Core workflow

1. Read `reference/career/profile.md` first for source-of-truth career facts.
2. Read `reference/career/tailoring-guide.md` if tailoring or summary changes are needed.
3. If `reference/career/cv/latex/tailored/<company>/job-description.md` already exists, read that first when reviewing or continuing a tailored packet.
4. If the tailored JD snapshot does not exist yet, read the relevant JD from `reference/career/job-tracker/` or the user-provided source, then store a frozen copy beside the tailored files as `cv/latex/tailored/<company>/job-description.md` so later review is self-contained.
5. When starting a new tailored packet, initialize it with `cv.py init --company <slug>` instead of manually copying files.
6. Keep the base LaTeX files in `cv/latex/base/` clean and generic.
7. Put company-specific versions in `cv/latex/tailored/<company>/`.
8. Never invent experience, skills, tools, certifications, customers, or outcomes.
9. Compile and visually review before calling the output done.

## Build and review

Use the bundled script when possible:

```bash
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py init --company synthesia
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py init --company synthesia --no-input --json
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py build --kind resume
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py build --kind resume --company synthesia
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py review --kind resume --company synthesia
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py build --kind resume --company synthesia --no-input --json
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py review --kind resume --company synthesia --no-input --json
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py clean
```

The script expects to run from somewhere inside the target repo and will discover the repo root automatically.
JSON is the default contract. Use `--plain` only for quick operator inspection. The CLI also accepts `--no-input` and `--version`.
`cv.py review` is the self-contained review path for this skill: it finds the repo-local compiled PDF for the requested `kind` and optional `company`, renders per-page PNGs into a temp review directory, and returns the source path, PDF path, review directory, and page image paths in JSON. The PDF is the primary review artifact. The colocated `job-description.md` is role-fit context for the review, not a separate review mode. This is the intended loop for both the main agent and any spawned reviewer/subagent.

## Tailoring rules

- Start a new tailored version with `cv.py init --company <slug>`, which copies the current base files and creates a colocated `job-description.md` placeholder. Do not reformat from scratch. The base carries the canonical preamble, custom commands, spacing system, section ordering, and capitalization conventions; tailoring is content work, not template work.
- Change the summary first. Sentence 1 should name the identity the role is hiring for. Sentence 2 should state what you want to do next, framed in the role's vocabulary.
- Reorder Experience bullets to surface role-relevant signals first. Customer-facing or domain-specific bullets should appear in position 1 or 2, not buried at the bottom.
- Prefer emphasis shifts over content expansion. Reword and reorder before adding new claims.
- Trim the Skills lines per category so each fits on one visual line. Wrapping reads as keyword stuffing.
- The Relevant Public Work section is OPTIONAL and role-dependent. Keep it for roles that explicitly value public teaching, community contribution, technical writing, developer advocacy, or forward-deployed engineering. Remove it for formal corporate or non-public-facing roles.
- Save tailored versions under `tailored/<company>/` rather than overwriting the base.
- Store the exact role snapshot as `tailored/<company>/job-description.md` in the same folder as the tailored resume and cover letter.
- The colocated JD snapshot is the audit artifact for that tailored packet. `job-tracker/` can still hold broader search notes, intake, or discovery links, but the reviewer should not have to leave the tailored folder to see what the resume was tailored against.
- Keep cover letters alongside the tailored resume for the same company.
- If the user has only raw notes, normalize them into `profile.md` before heavy tailoring.
- Never invent experience, skills, tools, certifications, customers, or outcomes.

For the full structural and formatting rules, read `references/template-patterns.md`.

## Visual checks

After compiling, render and inspect the PDF pages. Review the PDF itself, not extracted text.

Quick checks:
- clipped text
- overlapping elements
- inconsistent spacing
- awkward page breaks
- dates drifting out of alignment
- obvious underfilled second pages
- orphaned single-line fragments at the top of page 2
- links that do not look clickable because the link color is too dark

For a full audit, including typography, spacing, color, and a scoring rubric
that can be run by a reviewer or a sub-agent, read
`references/visual-review-heuristics.md`. Use that file when polishing a
tailored resume for a specific role or when the user is not happy with how the
resume looks but cannot name the issue.

When the resume is tailored for a specific role, review the PDF against the
colocated `job-description.md` with two lenses:
- visual quality from the rendered pages
- role fit from what the PDF actually surfaces on page 1 and page 2

Do not run a separate primary "text review" workflow. Use the PDF as the
single source of review truth, then edit the `.tex` only after issues are
identified.

## Output hygiene

Track source `.tex`, tailored `job-description.md`, and notes files.
Ignore generated PDFs and LaTeX build artifacts via `reference/career/cv/latex/.gitignore`.
