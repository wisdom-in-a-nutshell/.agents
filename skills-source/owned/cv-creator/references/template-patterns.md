# Resume Template Patterns

Codified structural conventions for the LaTeX resume template in this workspace.
Use this file when you need to add a new section, change formatting, or
understand why the base `resume.tex` looks the way it does.

For audit and review heuristics see `visual-review-heuristics.md`.
For folder layout see `structure-contract.md`.

## Table of contents

1. Document conventions
2. Preamble: packages and colors
3. Spacing system
4. Custom commands
5. Section structure and ordering
6. Header convention
7. Section conventions
8. Tailoring rules
9. Common modification patterns

## 1. Document conventions

- `documentclass`: 11pt, a4paper. European Lebenslauf default.
- Page geometry: 0.75in top, 0.7in bottom, 0.8in left/right. Tighter than US
  letter resume defaults.
- One or two pages. The current base template is optimized for two pages for
  experienced EU candidates, but page 2 must earn its space. Do not force a
  weak second page.
- Body font: TeX Gyre Pagella (Palatino-derived workhorse serif). Set via
  `fontspec`. Pagella renders well on screen and print, has good kerning, and
  reads as professional without being distinctive.
- Body text: `\raggedright` set inside `\begin{document}`. Justified body text
  with the relatively short measure of a resume creates word-spacing rivers.

## 2. Preamble: packages and colors

Required packages:

```latex
\usepackage[top=0.75in, bottom=0.7in, left=0.8in, right=0.8in]{geometry}
\usepackage{enumitem}    % itemize tuning, label customization
\usepackage{titlesec}    % section heading control
\usepackage{hyperref}    % clickable links
\usepackage{xcolor}      % color definitions
\usepackage{parskip}     % space between paragraphs (then override)
\usepackage{fontspec}    % requires xelatex or tectonic for OpenType
\usepackage{fontawesome} % icons in header
```

Three colors with three jobs. Do not add a fourth.

```latex
\definecolor{accent}{HTML}{2C3E50}    % section headings, rules
\definecolor{datecolor}{HTML}{555555} % dates, secondary labels
\definecolor{linkcolor}{HTML}{1F6FEB} % clickable links
```

`linkcolor` must be bright enough to look obviously clickable. A dark navy
link blends with section headings and looks dead. Do not change to a darker
shade for "elegance."

`accent` and `linkcolor` must be different. They have different jobs.

## 3. Spacing system

The single biggest source of ugly resumes is inconsistent spacing. The
template pins each spacing knob explicitly.

```latex
\setlength{\parskip}{2pt}                                % override parskip default
\titlespacing*{\section}{0pt}{10pt}{4pt}                 % section above/below
\setlist[itemize]{leftmargin=1.2em, itemsep=2pt,
                  parsep=0pt, topsep=2pt, partopsep=0pt,
                  label=--}                              % itemize tuning
```

Why:

- The `parskip` package default is about half a baselineskip (5-6pt). Combined
  with itemize `topsep` (default 4-6pt) and the role command's trailing
  vspace, this produces 10-12pt of empty space between a role's subtitle and
  its first bullet. That looks like a typo. Pinning `parskip` to 2pt and
  `topsep` to 2pt fixes it.
- `titlespacing*` `{0pt}{10pt}{4pt}` means: no left indent, 10pt space before,
  4pt space after the section heading. This balances heading prominence with
  content-side breathing room.
- itemize `label=--` uses an en-dash bullet marker. Cleaner than the default
  black bullet for a serif resume.

Resulting visual rhythm:

- Gap between role subtitle and first bullet: ~4-5pt.
- Gap between one role's last bullet and the next role's title: ~8-10pt.
- Gap between section heading rule and first content line: ~4-6pt.
- Gap between sections: ~10-12pt.

## 4. Custom commands

### `\role{title}{location}{org}{dates}`

Two-line role header for Experience and Education entries.

```latex
\newcommand{\role}[4]{%
  \vspace{6pt}
  {\textbf{#1}\hfill\textit{#2}}\\[1pt]
  {\textit{#3}\hfill\textcolor{datecolor}{#4}}%
  \vspace{-3pt}%
}
```

- Line 1: bold title left, italic location right.
- Line 2: italic org left, gray date right.
- Trailing `\vspace{-3pt}` compensates for the parskip + topsep that follows
  when an `itemize` block starts immediately after.
- Org should be wrapped in `\href{...}` when a canonical URL exists.

### `\labelrow{label}{content}`

Two-column row used for Skills and Details sections. Built from two
side-by-side `minipage`s.

```latex
\newlength{\labelcolwidth}
\setlength{\labelcolwidth}{3cm}

\newcommand{\labelrow}[2]{%
  \par\noindent
  \begin{minipage}[t]{\labelcolwidth}%
    \textcolor{datecolor}{\textbf{#1}}%
  \end{minipage}%
  \begin{minipage}[t]{\dimexpr\linewidth-\labelcolwidth\relax}%
    \raggedright #2%
  \end{minipage}%
  \par\vspace{5pt}%
}
```

Why minipages and not `\makebox` + `\hangindent`:

- `\makebox` only sets the indent for the first line. When content wraps, the
  wrapped line goes back to the left margin, breaking the column alignment.
- `\hangindent` is a paragraph-level setting that conflicts with `\makebox`.
- Two side-by-side `minipage`s give the content its own width context, so
  wrapped lines stay inside the content column. This is the equivalent of a
  hanging indent without the conflict.

Label width is 3cm. Wider labels overflow visually; shorter labels look fine
inside a wider box. Do not use labels longer than ~14 characters in this
column width.

Label style is bold + datecolor gray, NOT small caps. Small caps treat
already-uppercase letters (like "AI") differently from the rest, producing
visible inconsistency. Bold + gray recedes visually so the label functions as
a column header instead of a competing heading.

### `\sep`

Light vertical bar used between header link items.

```latex
\newcommand{\sep}{\enspace\textcolor{datecolor}{\textbar}\enspace}
```

## 5. Section structure and ordering

Base-template order for an IC technical role:

1. Summary
2. Experience
3. Patents (if any)
4. Selected Publications (if any)
5. \pagebreak (common default when page 2 is earned)
6. Relevant Public Work (optional, role-dependent)
7. Education
8. Skills
9. Details

The base template often uses `\pagebreak` between Selected Publications and
Relevant Public Work so page 2 starts cleanly with a role-relevant proof
section instead of a half-orphaned Education heading. Keep that break when
page 2 is earned. Remove or move it if it creates a weak or underfilled page 2.

For a PM or research role, consider moving Education above Experience.

## 6. Header convention

```latex
\begin{center}
  {\LARGE\bfseries Name}\\[5pt]
  {\small
    \faMapMarker\enspace City, Country \sep
    \href{mailto:...}{\faEnvelope\enspace email} \sep
    \href{...}{\faGlobe\enspace site} \sep
    \href{...}{\faLinkedin\enspace LinkedIn} \sep
    \href{...}{\faGithub\enspace GitHub}
  }
\end{center}
```

Single-line contact row separated by `\sep`. Do NOT include "(permanent
resident)" or visa status in the header. That information belongs in the
Details section. Putting it in the header reads defensive.

Do NOT include phone number in the header for a digital application. The form
already collects it.

## 7. Section conventions

### Summary

- 3 to 5 sentences.
- Sentence 1: name the identity the role is hiring for. For a Codex Deployment
  Engineer, open with "Early power user of OpenAI Codex." For a research
  engineer role, open with "Engineer who ships X in production."
- Sentence 2: state what you want to do next, framed in the role's vocabulary.
- Sentence 3-4: current work, past credibility, public proof signal.
- Body text, not bullets. Justified-feeling but ragged-right.

### Experience

- 1-4 bullets per role. Less is a stub. More is a dump.
- Each bullet leads with a verb in past or present tense ("Built", "Scoped",
  "Designed", "Use", "Embedded", "Scaled", "Chief-authored").
- Customer-facing or role-specific signal should appear in bullet #1 or #2.
- Do NOT repeat skills here that appear in the Skills section unless they are
  load-bearing for the bullet's claim.

### Patents

- Title (linked) + (year). Nothing else.
- Do NOT include patent numbers. The hyperlink leads to the page that has the
  number.
- Do NOT include the assignee company if it is already in Experience. That is
  redundant.

### Selected Publications

- Title (linked) + (Cited by N). Capital C in "Cited by" to match Google
  Scholar's UI label and the Title Case convention used in other parenthetical
  labels.
- 3-5 entries.
- Last bullet: "See full list of publications on [Google Scholar](url)." This
  is the canonical home for the full-list link in the current template family.
  Do NOT scatter Scholar links across multiple sections.

### Relevant Public Work

- OPTIONAL section. Include only when the role explicitly values public
  teaching, community contribution, technical writing, developer advocacy, or
  forward-deployed engineering.
- Keep it only when it directly strengthens fit for the target JD. If it is
  weakly related, stale, or less relevant than another proof signal, compress
  it into the summary or drop it entirely.
- Use `\labelrow` with channel labels: YouTube, Blog, Reddit, X, Talks, etc.
- Each row should lead with one named flagship piece (in italics or quoted),
  followed by numbered links for the rest if there are more than 1-2 items.
- Keep total to 3-4 channel rows. More feels like an appendix.

### Education

- Use `\role{}{}{}{}` for each entry.
- One bullet per entry, max two.
- Lead with notable distinctions (grade with distinction, thesis honors, etc.)
- Hyperlink the school name when it has a canonical site.

### Skills

- Use `\labelrow` with category labels.
- Default categories: AI Systems, Engineering, Infrastructure, plus one
  role-relevant fourth (Engagement / Domain / Field Work / Production / etc.)
- Each labelrow content must fit on ONE visual line. If it wraps, trim items.
  A long category with 12 tools reads as keyword stuffing; a tight category
  with 5-6 tools reads as confident.
- Capitalize the first word of each comma-separated item (Title Case on first
  word). This makes every item read as a labeled tag, not running prose.
- Proper nouns (Python, Azure, MCP) keep their natural capitalization.

### Details

- Use `\labelrow` for: Languages, Work authorization, Travel, Relocation.
- Languages format: `English (Fluent), German (Basic, A2), Tamil (Native),
  Hindi, Telugu, Kannada`. Capitalize proficiency descriptors in parentheses
  for consistency with the Title Case convention elsewhere.
- Work auth row: state residency, visa requirement, and sponsorship status.
- Travel row: percent willingness.
- Relocation row: open cities or regions.
- Do not add a Research row by default. Keep the Google Scholar full-list link
  under Selected Publications unless a specific template variant truly lacks
  that section.

## 8. Tailoring rules

When creating a tailored version under `cv/latex/tailored/<company>/`:

1. Initialize the tailored packet with `cv.py init --company <slug>` first.
2. Rewrite the Summary to lead with role-specific identity.
3. Reorder Experience bullets to surface role-relevant signals first.
4. Trim or remove the Relevant Public Work section if the role does not
   explicitly value public teaching or community contribution, or if the public
   work does not materially strengthen fit.
5. Trim Skills items per category so each line fits on one visual line.
6. Optionally rename the fourth Skills category to fit the role
   (Engagement / Domain / Production / etc.)
7. Do NOT invent new content. All facts must come from `profile.md`,
   `tailoring-guide.md`, or the user.
8. Build with `cv.py build --kind resume --company <slug>`.
9. Review with `cv.py review --kind resume --company <slug>`.
10. Audit against `visual-review-heuristics.md` rubric.

## 9. Common modification patterns

### Add a new section between two existing sections

Place the `\section{...}` and content after the end of the section that should
come before it. The standard ordering in section 5 of this file should be
followed unless there is a clear reason to deviate.

### Add a new label row to Skills or Details

Use `\labelrow{Label}{Content}`. Label should be 1-2 words and fit in 3cm.
Content should fit on one visual line.

### Force a section to start on page 2

Use `\pagebreak` before the section heading when it improves page balance. The
current base template often does this before "Relevant Public Work," but do not
keep it mechanically if page 2 becomes weak.

### Reduce the label column width

Change `\setlength{\labelcolwidth}{3cm}` to a smaller value. Note that
labels longer than the new width will visually overflow into the content
column. Test by re-rendering.

### Increase content density

Reduce the role command's leading `\vspace{6pt}` to `4pt` and the global
`\parskip` from `2pt` to `1pt`. Do not go below those values; the document
will start to feel cramped.

### Switch the workhorse serif

The fontspec setup uses TeX Gyre Pagella. To switch to Charter:

```latex
\setmainfont{XCharter}[
  Extension = .otf,
  UprightFont = *-Roman,
  BoldFont = *-Bold,
  ItalicFont = *-Italic,
  BoldItalicFont = *-BoldItalic,
]
```

Pagella is the default because it is widely available, has full bold/italic
weights, and renders well on both screen and print.
