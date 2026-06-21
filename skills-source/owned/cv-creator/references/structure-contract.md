# CV Creator Structure Contract

## Minimal layout

Durable career memory (tracked, committed) and disposable tailored packets
(gitignored, throwaway) live in two different places on purpose.

```text
<career-root>/                 # DURABLE — tracked career memory
  overview.md
  profile.md
  tailoring-guide.md
  job-tracker/
  cv/
    latex/
      .gitignore
      base/
        resume.tex
        cover-letter.tex

<repo-root>/                    # DISPOSABLE — gitignored, cleared when done
  tmp/
    cv/
      tailored/
        <company>/
          job-description.md
          resume.tex
          cover-letter.tex
```

The CLI resolves both locations automatically. `cv.py clean` removes the
disposable `tmp/cv/` tree (plus the render temp). The repo's `tmp/` must be
gitignored — every supported repo already ignores it.


## Career root detection

The shared CLI auto-detects the career root from repo-local files. Supported roots are:

- `memory/areas/career/` — direct career area, used by focused personal workspaces such as Angie.
- `memory/areas/builder/career/` — nested career area, used when career belongs under a broader builder area such as Adi.

If both exist and contain career signals, pass `--career-root <path>` to the CLI. Do not duplicate the same CV packet under both roots.

## Intent

- `profile.md` is the source of truth for education, work history, skills, links, publications, patents, and summary ingredients.
- `tailoring-guide.md` captures positioning rules, keyword sets, and what not to invent.
- `base/` holds the generic default LaTeX files.
- `tmp/cv/tailored/<company>/` (disposable, under repo root) holds the self-contained tailored packet: the exact job description snapshot, tailored resume, and tailored cover letter. It is a one-application rendering of durable canon, not memory — it is gitignored and cleared when the work is done.
- `job-tracker/` may still hold discovery notes, search results, and broader application tracking, but the exact JD used for a tailored packet should be copied into the matching `tmp/cv/tailored/<company>/job-description.md` so later audits do not depend on cross-folder lookup.

## Migration guidance

When migrating from a flat `latex/` folder:

- Move the generic resume to `base/resume.tex`.
- Create `base/cover-letter.tex` if one does not exist yet.
- Let `cv.py init --company <slug>` create the tailored packet under `tmp/cv/tailored/<company>/` rather than copying files into the tracked tree.
- If a role-specific JD exists elsewhere, copy it to `tmp/cv/tailored/<company>/job-description.md`.
- If older tailored files were committed under `<career-root>/cv/latex/tailored/`, treat them as legacy: remove them from the tracked tree once the application is closed (the durable facts already live in `profile.md`/canon).
- Keep existing raw notes and draft markdown files if they still help.

## Git ignore

Keep a `.gitignore` inside `<career-root>/cv/latex/` that ignores build products like:

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

Track only the durable `base/` `.tex` sources. Tailored packets and their
`job-description.md` snapshots live under the repo's gitignored `tmp/cv/` and
are never committed — they are disposable renderings, not memory.
