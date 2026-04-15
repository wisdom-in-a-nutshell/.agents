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
2. Read `reference/career/tailoring-guide.md` if tailoring or summary changes are needed. Pay particular attention to the "Competitor awareness" section, which governs how to handle product-level references to the target company's rivals (e.g. do not send an Anthropic application full of Codex name-drops).
3. If `reference/career/cv/latex/tailored/<company>/job-description.md` already exists, read that first when reviewing or continuing a tailored packet.
4. If the tailored JD snapshot does not exist yet, read the relevant JD from `reference/career/job-tracker/` or the user-provided source, then store a frozen copy beside the tailored files as `cv/latex/tailored/<company>/job-description.md` so later review is self-contained.
5. When starting a new tailored packet, initialize it with `cv.py init --company <slug>` instead of manually copying files.
6. Keep the base LaTeX files in `cv/latex/base/` clean and generic.
7. Put company-specific versions in `cv/latex/tailored/<company>/`.
8. Never invent experience, skills, tools, certifications, customers, or outcomes.
9. Compile and visually review before calling the output done.
10. Before committing the final PDF, run a competitor-awareness grep against the target's rival products and companies. See the "Competitor awareness" section of `tailoring-guide.md` for the current map and the audit checklist.

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
- **Competitor awareness**: before compiling, audit the `.tex` files for prominent references to the target company's direct rivals. Do not send a resume that reads as a love letter to the target's competitor. See the repo-local `reference/career/tailoring-guide.md` "Competitor awareness" section for the current competitor map, rewrite strategies, and audit checklist. Reframe product-level name-drops (Codex, Claude, ChatGPT) into category-level language (agent harness, coding agent, LLM application engineering) when the target is a rival's rival.

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

## Submitting applications via browser

When the user asks you to actually submit a compiled CV to a web form, do NOT reach for the Claude-in-Chrome `file_upload` tool. It is broken as of 2026-04-15 (CDP error `-32000 "Not allowed"` on all origins, tracked as [anthropics/claude-code#32561](https://github.com/anthropics/claude-code/issues/32561)). Attempting it wastes time and blocks the rest of the submission.

Use the `agent-browser` CLI instead. It drives Chrome via CDP directly with no extension bridge and handles file uploads cleanly.

### Canonical submission flow

```bash
# 1. Open the application page in agent-browser
agent-browser open "<application-url>"
agent-browser wait --load networkidle

# 2. Get the accessibility tree with element refs
agent-browser snapshot -i

# 3. Fill text fields and click radios/buttons using the @eN refs
agent-browser fill @e13 "Adithyan Ilangovan"
agent-browser fill @e14 "adi@aipodcast.ing"
agent-browser click @e33  # radio button
agent-browser click @e5   # combobox option after fill

# 4. Upload resume + cover letter PDFs (this is the bit Claude-in-Chrome cannot do)
agent-browser upload @e15 "/Users/dobby/GitHub/adi/reference/career/cv/latex/tailored/<slug>/resume.pdf"
agent-browser upload @eN "/Users/dobby/GitHub/adi/reference/career/cv/latex/tailored/<slug>/cover-letter.pdf"

# 5. Screenshot for verification before the final click
agent-browser screenshot /tmp/<slug>-before-submit.png

# 6. Submit
agent-browser click @eN  # submit button
agent-browser wait --load networkidle
agent-browser screenshot /tmp/<slug>-after-submit.png
```

### Workflow notes

- Combobox selection is a two-step dance: `fill` then `click` the matching option ref. The option ref appears in a fresh `snapshot -i` after the fill.
- `agent-browser` uses a separate Chrome instance from Claude-in-Chrome. Any login state from the extension does not carry over. Most Ashby/Greenhouse/Lever application forms do not require login, so this is usually fine.
- Before every `click @eN` on a submit button, take a screenshot and show it to the user. Submission is irreversible.
- After submission, capture a confirmation screenshot (`agent-browser screenshot`) as evidence and note the result in the relevant tracker file (e.g. `capture/job-applications-<date>/STATUS.md`).
- If the form has many essay questions, draft all answers before opening the form and fill them in a single pass. Reviewing drafts in source is easier than scrolling a populated form.
- **Refs renumber aggressively.** Any interaction that changes the DOM (combobox selection, radio click, upload) can shift every ref below it by one. If you drafted fills using refs from an early snapshot and then interacted with the form, your essays will land in the wrong fields. Always re-snapshot right before a batch of fills, and verify filled content with `agent-browser eval` after.
- **Ashby has invisible reCAPTCHA and will flag automated submissions as spam.** The form will appear to submit successfully, then replace itself with "Your application submission was flagged as possible spam. If you believe this was a mistake, please submit your application again." The reCAPTCHA token is generated from user gesture signals (mouse movement, genuine clicks, focus patterns) that programmatic fills do not produce. Retry does not help. Presence of `textarea[name=g-recaptcha-response]` on the form is the tell.
  - **Workaround**: fill everything with agent-browser, verify the filled state in a screenshot, then hand the already-filled form to Adi and ask him to click Submit. Same handoff pattern as the Chrome file_upload workaround.
  - Do NOT close the agent-browser window after filling. Adi needs the populated tab still open to click Submit.
  - Greenhouse and Lever do not generally trip this. Ashby is the problem surface.

### When to prefer Claude-in-Chrome

Claude-in-Chrome is still the right tool when the task needs an already-logged-in session, cookies, or extensions you have configured in your daily browser. For stateless public application forms, agent-browser is simpler and more reliable.
