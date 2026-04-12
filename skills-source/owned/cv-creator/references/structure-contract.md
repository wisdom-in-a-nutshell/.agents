# CV Creator Structure Contract

## Minimal layout

```text
reference/career/
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
          resume.tex
          cover-letter.tex
```

## Intent

- `profile.md` is the source of truth for education, work history, skills, links, publications, patents, and summary ingredients.
- `tailoring-guide.md` captures positioning rules, keyword sets, and what not to invent.
- `base/` holds the generic default LaTeX files.
- `tailored/<company>/` holds company-specific copies.

## Migration guidance

When migrating from a flat `latex/` folder:

- Move the generic resume to `base/resume.tex`.
- Create `base/cover-letter.tex` if one does not exist yet.
- Move `resume-<company>.tex` to `tailored/<company>/resume.tex`.
- Move `cover-letter-<company>.tex` to `tailored/<company>/cover-letter.tex`.
- Keep existing raw notes and draft markdown files if they still help.

## Git ignore

Keep a `.gitignore` inside `reference/career/cv/latex/` that ignores build products like:

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

Track the `.tex` sources.
