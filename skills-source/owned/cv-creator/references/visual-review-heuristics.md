# Visual Review Heuristics

Use this file when you need to audit a compiled resume or cover letter PDF for
visual, typographic, and structural quality before calling the output done.

The goal is a resume that (1) reads well to a skimming hiring manager in under
30 seconds, (2) holds up under close inspection, and (3) matches the target
role without inventing content.

## Table of contents

1. How to run the review loop
2. Typography heuristics
3. Layout heuristics
4. Spacing heuristics
5. Color and link heuristics
6. Content heuristics
7. Page break and orphan heuristics
8. Common problems and their fixes
9. Visual review scoring rubric
10. Future improvements

## 1. How to run the review loop

The review loop is: render -> audit -> fix -> re-render. Small steps, always
PDF-first and visual.

1. Build the target PDF using `scripts/cv.py build`.
2. Render the PDF to PNG at 150 DPI using `pdftoppm -png -r 150 <pdf>
   <out-prefix>`.
3. Read the rendered PNGs (use the Read tool or equivalent) and apply the
   heuristics in this file.
4. Fix any issues in the `.tex` source.
5. Re-run `cv.py build` and `pdftoppm`, then re-audit.
6. Stop only when the rubric in section 9 scores cleanly or the user is
   explicitly happy.

If `cv.py review` exists in the skill, it already handles rendering to a
temporary directory, so prefer it:

```bash
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py build --kind resume --company <slug>
python3 ~/.agents/skills-source/owned/cv-creator/scripts/cv.py review --kind resume --company <slug>
```

The review command is intentionally self-contained around the repo contract. It
does not take an arbitrary PDF path. Instead, it resolves the expected
repo-local source/PDF pair and returns the rendered page PNG paths plus the
review directory in JSON so the main agent or a reviewer/subagent can inspect
the images directly. The compiled PDF is the primary review artifact. The
colocated `job-description.md` is context for judging role fit, not a separate
review surface.

Do not rely on text-only extraction from the PDF. Text extraction hides
spacing, alignment, page breaks, and color. Always inspect a raster render.
Do not create a separate primary text-review workflow. Review the PDF itself,
then use the JD to ask whether the right signals are actually visible in the
document the hiring team would read.

## 2. Typography heuristics

- Body font is a serif workhorse (Pagella, Minion, Charter). It should be
  invisible, not distinctive. If the reader notices the font, it is wrong.
- Base size is 10-11 pt for a European Lebenslauf, 11 pt default for this
  skill.
- Hierarchy should be clear and have exactly three levels:
  1. Name at the top, largest (~20 pt).
  2. Section headings (~13 pt, bold, accent color, horizontal rule).
  3. Body and role titles at base size.
- Do not mix more than two families. Stick to one serif family with italic,
  bold, and regular variants.
- Italic is for subtitles, company names, and journal names. Bold is for role
  titles, section headings, and emphasized keywords. Underline is never used.
- Use en-dash (`--`) for date ranges and as the bullet marker. Reserve em-dash
  for inline separators inside prose. Do not use U+2011, U+2013, or U+2014
  literal characters; use LaTeX's `--` and `---`.
- Set `\raggedright` globally for the body. Justified text with a short line
  measure creates word-spacing rivers. A resume reads faster ragged-right and
  is less fatiguing.

## 3. Layout heuristics

- Margins: 0.7-0.9 in on all sides. Tighter than 0.7 feels cramped; wider than
  0.9 wastes space.
- Page count: one or two. Two is fine for European candidates with substantial
  experience. Three is almost always wrong.
- Page 1 must carry the strongest content for the target role. If the hiring
  manager only reads page 1, the decision should be possible from page 1.
- Page 2 must earn its space. Do not push a tiny tail to page 2. If page 2
  would be less than about 30% full, pull content back or restructure.
- Section order for IC technical roles:
  1. Summary
  2. Experience
  3. Patents (if any)
  4. Selected Publications (if any)
  5. Relevant Public Work (optional, only if it strengthens JD fit)
  6. Education
  7. Skills
  8. Details (Languages, Work authorization, Travel, Relocation, optional Research)
- For PM or leadership roles, Education may move higher.
- Right-align dates. Keep them in a subtle gray (`datecolor`) so they do not
  compete with titles.
- Use a single accent color for section headings. Two accent colors almost
  always fight.

## 4. Spacing heuristics

The single biggest source of ugly resumes is inconsistent spacing. Apply these
rules.

- Set `\parskip` explicitly. The default of the `parskip` package (about half a
  baseline skip) combined with itemize `topsep` and `\role` trailing vspace
  stacks up to 10-12 pt of gap between role subtitles and bullets, which looks
  like a typo. Set `\parskip` to around 2 pt and compensate in `topsep` and
  `\role`.
- itemize `topsep` should be 2 pt, not the default 4-6 pt.
- Section spacing: `\titlespacing*{\section}{0pt}{10pt}{4pt}` works well for 11
  pt body.
- Role command should have about 6 pt vspace before and a small negative vspace
  (about -3 pt) after to compensate for paragraph-to-list transition.
- Between skill rows or details rows, use explicit `\\[6pt]` inside a
  `flushleft` block. Do not rely on `\par` or `parskip` because they inherit
  unpredictable values.
- Check that:
  - Gap between role subtitle and first bullet is about 4-6 pt.
  - Gap between one role's last bullet and the next role's title is about 8-10
    pt.
  - Gap between section heading rule and first content line is about 4-6 pt.
  - Gap between sections is about 10-12 pt.
- The rhythm should feel like a breathing document, not a crammed page or an
  airy brochure.

## 5. Color and link heuristics

- The resume will usually be read on screen, so links must be obviously
  clickable. Use a bright blue (around `#1F6FEB`) for link color.
- A dark navy link (around `#2C3E50`) blends with section headings and looks
  unclickable. Do not use it as a link color even if it is tonally prettier.
- The accent color (for headings, rule lines, bold labels in Skills and
  Details) should be a distinct darker navy (`#2C3E50`). Accent and link
  are related but not identical. Keep them separate.
- Date color should be a medium gray (`#555555`). Not black, not too light.
- Never use red or orange. Save those for rare emphasis or not at all.
- Hyperlink everything that has a canonical destination: company names in
  Experience, school names in Education, patent titles, publication titles,
  public profile links (GitHub, LinkedIn, blog, Scholar), and the Google
  Scholar "full publications list" link.
- Do not hyperlink the assignee company in patent lines if the company is
  already linked in the Experience section. Redundant links add noise without
  adding information.

## 6. Content heuristics

- Start the Summary by naming the identity the role is hiring for. For a Codex
  Deployment Engineer, open with "early power user of Codex." For a research
  engineer role, open with "engineer with [X] shipped systems." Do not bury the
  role-specific identity behind general background.
- Review the Skills section against the JD, not against a generic master list.
  If the JD emphasizes customer workshops, public speaking, solutions
  architecture, deployment, security, or a domain specialization, surface the
  matching true skills visibly in the PDF. If a claimed skill is not supported
  by the person's real experience, do not add it.
- Public proof-of-work belongs in the Summary as a one-clause signal (for
  example, "shipping what I learn as blog posts, YouTube videos, and Reddit
  writeups that regularly trend in r/codex"). The actual links live in the
  cover letter, not in the resume body.
- If the role explicitly values public contributions, consider adding a
  dedicated section called "Selected Public Work" or "Relevant Public Work."
  In the current template family this usually lives at the top of page 2, not
  above Experience. This is a conditional pattern, not a default.
- Keep a dedicated public-work section only when it directly strengthens fit
  for the target JD. If the public work is weakly related, stale, or less
  relevant than another signal, compress it into the summary or drop it.
- Every Experience role should have 1-4 bullets. Less than 1 reads like a
  stub. More than 4 reads like a dump.
- Bullets should lead with a verb and a concrete outcome. Avoid "responsible
  for" and "worked on." Avoid padding adverbs.
- The Skills section should be categorized, and each category should fit on
  one visual line. If a category wraps to two lines, cut items until it fits.
  A long category with 12 tools reads as keyword stuffing; a tight category
  with 5-6 tools reads as confident.
- Suggested skills categories: `AI Systems`, `Engineering`, `Infrastructure`,
  plus one role-relevant fourth category (`Domain`, `Engagement`, `Production`,
  `Field Work`, etc.). Adjust category names to the role.
- Languages line is not a sentence. Do not end it with a period.
- Always include a Details section near the bottom with these rows:
  - `Work authorization` (residency, visa status, whether sponsorship is
    required)
  - `Travel` (percent willing to travel)
  - `Relocation` (cities or regions the person is open to)
- The "full publications list" must be linked somewhere on the resume. The
  cleanest home in the current template family is the final line or bullet
  under Selected Publications. Do not scatter Scholar links across multiple
  sections.
- Patents should show title (linked) + year. Do not repeat the assignee
  company or patent number if the patent page is already linked.
- Never invent content. If a fact is not in `profile.md` or the online
  resume, do not add it. See `tailoring-guide.md` for the canonical rule.
- Dates should be consistent in format. Prefer year-only ("2024 - Present") for
  past roles and the current role. Do not mix "Jan 2024" with "2022 - 2023".

## 7. Page break and orphan heuristics

- A section heading must not be the last line on a page. If it is, push the
  section down with `\pagebreak` or tighten content above.
- A single line of a multi-line sentence must not orphan at the top of page 2.
  If it does, inline the sentence, tighten the previous section, or move the
  content into a sibling section.
- A section should either fit entirely on one page or split cleanly at a
  subsection boundary. A section split after its heading and first line only
  is ugly.
- If the Selected Publications section splits across pages, prefer to push the
  whole section to the next page with `\pagebreak`, or put the "Full list on
  Google Scholar" line at the end of that section instead of orphaning it.
- Do not use manual `\newpage` inside a role entry or inside a list.
- After any `\newpage` or `\pagebreak` insertion, re-render and check that
  nothing else shifted badly.

## 8. Common problems and their fixes

| Problem                                    | Fix                                                               |
| ------------------------------------------ | ----------------------------------------------------------------- |
| Wide gap between role subtitle and bullet  | Reduce `\parskip` to 2 pt and `topsep` to 2 pt                    |
| Skill line wraps to two lines              | Cut 3-5 items from the category until it fits on one line         |
| Page 2 has only a few lines                | Pull content back, remove `\newpage`, or move a section           |
| Body text has obvious word-spacing rivers  | Add `\raggedright` globally                                       |
| Orphan sentence at top of page 2           | Inline the sentence or tighten the preceding section             |
| Link color looks unclickable               | Use bright blue (`#1F6FEB`), not dark navy                        |
| Redundant assignee on patent lines         | Remove the company name; it is already in Experience              |
| Hierarchy feels flat                       | Check that section headings use accent color and rule             |
| Dates inconsistent month vs year           | Normalize to year-only for all but the current role               |
| Languages line ends with a period          | Remove the period                                                 |
| Skills tabular has wide gaps               | Replace with `flushleft` + `\\[6pt]` explicit rows                |
| "Permanent resident" in header             | Move it to the `Work authorization` row in Details                |
| Company italic subtitle is too loud (blue) | Keep link color bright but make sure the page has <= 6 blue spots |

## 9. Visual review scoring rubric

Use this rubric to score a resume before calling it done. Each item is 0 or 1.
Target: 15 out of 15. Below 13, iterate. Below 10, restructure.

```
[ ] 1. Summary opens with role-specific identity
[ ] 2. Dates are consistent and unambiguous across all sections
[ ] 3. Role titles match reality and are not inflated
[ ] 4. Every company, school, patent, and publication that can be hyperlinked is hyperlinked
[ ] 5. Every skills line fits on exactly one visual line
[ ] 6. No orphaned content at page tops
[ ] 7. Section spacings feel consistent to the eye
[ ] 8. Link color is bright enough to be obviously clickable
[ ] 9. Body text is ragged-right (no justified rivers)
[ ] 10. Page 1 carries the strongest content for the target role
[ ] 11. Page 2 is balanced, not nearly-empty nor crammed
[ ] 12. Details section includes work auth, travel, relocation
[ ] 13. A link to the full publications list exists under Selected Publications
[ ] 14. Section headings use consistent accent color and rule
[ ] 15. No section splits awkwardly across pages
```

If running this as an agent audit, output the rubric with each check explicitly
marked 0 or 1 and a one-line justification for each failure. Then propose the
smallest fix for each failure before making changes.

## 10. Future improvements

This file should grow as new patterns become durable.

Candidate improvements that are not yet the default but may be added later:

- **Automated visual review sub-agent.** The review loop in section 1 is
  currently manual. In future, a sub-agent could be spun up that:
  1. Builds and renders the PDF.
  2. Reads each rendered page.
  3. Evaluates against the rubric in section 9.
  4. Returns a scored report with suggested fixes.
  The parent agent can then decide which fixes to apply. Treat this file as the
  rubric contract for that sub-agent.

- **Per-role heuristic profiles.** Some heuristics change by role family
  (research engineer vs deployment engineer vs PM). Profiles could live as
  additional reference files under `references/profiles/<family>.md` and be
  loaded when the user explicitly targets that family.

- **Template fragment library.** Common fragments (Details section, Skills
  tabular replacement, Selected Public Work block) could live under
  `assets/fragments/` as reusable `.tex` snippets that `cv.py` can splice in.

- **Typography audit at two scales.** Render at both 100 DPI (for page-level
  layout audit) and 300 DPI (for letterform audit). Currently 150 DPI is the
  default and it is a decent compromise.

- **Link liveness check.** After compilation, crawl the extracted URLs from
  the PDF and check for 200 responses. This catches stale links to old blog
  posts, patents, or publications.
