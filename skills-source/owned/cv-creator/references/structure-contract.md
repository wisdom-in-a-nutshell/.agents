# CV Creator Structure Contract

## Minimal layout

```text
memory/areas/builder/career/
  README.md
  profile.md
  tailoring-guide.md
  job-tracker/
  cv/
    latex/
      .gitignore
      base/
        resume.tex
        cover-letter.tex
      tailored/
        <company>/
          job-description.md
          resume.tex
          cover-letter.tex
```

## Intent

- `profile.md` is the source of truth for education, work history, skills, links, publications, patents, and summary ingredients.
- `tailoring-guide.md` captures positioning rules, keyword sets, and what not to invent.
- `base/` holds the generic default LaTeX files.
- `tailored/<company>/` holds the self-contained tailored packet: the exact job description snapshot, tailored resume, and tailored cover letter.
- `job-tracker/` may still hold discovery notes, search results, and broader application tracking, but the exact JD used for a tailored packet should be copied into the matching `tailored/<company>/job-description.md` so later audits do not depend on cross-folder lookup.

## Migration guidance

When migrating from a flat `latex/` folder:

- Move the generic resume to `base/resume.tex`.
- Create `base/cover-letter.tex` if one does not exist yet.
- If a role-specific JD exists elsewhere, copy it to `tailored/<company>/job-description.md`.
- Move `resume-<company>.tex` to `tailored/<company>/resume.tex`.
- Move `cover-letter-<company>.tex` to `tailored/<company>/cover-letter.tex`.
- Keep existing raw notes and draft markdown files if they still help.

## Git ignore

Keep a `.gitignore` inside `memory/areas/builder/career/cv/latex/` that ignores build products like:

- `*.pdf`
- `*.aux`
- `*.log`
- `*.out`
- `*.synctex.gz`
- `*.fls`
- `*.fdb_latexmk`
- `*.toc`
- `*.nav`
- `*.snm`
- `*.vrb`
- `*.bbl`
- `*.blg`
- `*.xdv`

Track the `.tex` sources and the tailored `job-description.md` snapshots.
