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
- `reference/career/cv/latex/tailored/<company>/resume.tex`
- `reference/career/cv/latex/tailored/<company>/cover-letter.tex`

If the contract is missing, create the minimal structure first instead of improvising files in random places.

Read `references/structure-contract.md` when you need the exact folder expectations or migration pattern.

## Core workflow

1. Read `reference/career/profile.md` first for source-of-truth career facts.
2. Read `reference/career/tailoring-guide.md` if tailoring or summary changes are needed.
3. Read the relevant JD from `reference/career/job-tracker/` when tailoring for a company.
4. Keep the base LaTeX files in `cv/latex/base/` clean and generic.
5. Put company-specific versions in `cv/latex/tailored/<company>/`.
6. Never invent experience, skills, tools, certifications, or outcomes.
7. Compile and visually review before calling the output done.

## Build and review

Use the bundled script when possible:

```bash
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py build --kind resume
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py build --kind resume --company synthesia
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py review --kind resume --company synthesia
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py build --kind resume --company synthesia --no-input --json
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py clean
```

The script expects to run from somewhere inside the target repo and will discover the repo root automatically.
JSON is the default contract. Use `--plain` only for quick operator inspection. The CLI also accepts `--no-input` and `--version`.

## Tailoring rules

- Change the summary first.
- Reorder bullets before rewriting them.
- Prefer emphasis shifts over content expansion.
- Save tailored versions under `tailored/<company>/` rather than overwriting the base.
- Keep cover letters alongside the tailored resume for the same company.
- If the user has only raw notes, normalize them into `profile.md` before heavy tailoring.

## Visual checks

After compiling, render and inspect the PDF pages.

Check for:
- clipped text
- overlapping elements
- inconsistent spacing
- awkward page breaks
- dates drifting out of alignment
- obvious underfilled second pages

## Output hygiene

Track source `.tex` and notes files.
Ignore generated PDFs and LaTeX build artifacts via `reference/career/cv/latex/.gitignore`.
