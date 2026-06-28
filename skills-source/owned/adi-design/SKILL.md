---
name: adi-design
description: Apply Adi's personal design language so his apps look like one cohesive product. Use when building, restyling, or reviewing any UI for Adi's personal projects (dobby-dashboard, blog/adithyan.io, ~/GitHub/agents/dashboard) or a new personal app/page, including choosing colors, typography, spacing, radius, or motion, setting up a theme or design tokens, migrating a surface off a generic or warm-cream look, or judging whether a screen is on-brand. The aesthetic is clean off-white (never warm cream), oklch sage accent with amber secondary, Newsreader serif for reading and Inter for UI, flat hairline surfaces, and restrained state-only motion.
---

# Adi Design

A calm reading room: clean off-white, sage accent, serif for reading, flat
hairline surfaces, restrained motion. The goal is that every one of Adi's apps
feels like one product made by one person with taste.

**Canon & showroom:** the source of truth is the `~/GitHub/adi-design` repo
(`system/styles.css` + `system/tokens/`), browsable live at
`https://design.adithyan.io`. It is authored in the Claude Design project and
exported into that repo. This skill carries a **vendored copy** of the identity +
tokens so you can build Adi's UIs in any repo without cloning — when the canon's
`VERSION` bumps, refresh `assets/tokens.css` from that repo's `system/styles.css`.

## Flow

1. Read `references/design-language.md` — the aesthetic, the rules, the
   do's/don'ts, and the per-product notes. This is the part that keeps work
   recognizably Adi's.
2. Use `assets/tokens.css` (a vendored copy of the canon) for values. Reference
   tokens (`var(--accent)`, `--space-lg`), never raw hex/oklch literals.
3. Wire the tokens into the target the way that stack consumes them (below).
4. Apply, then check against the hard rules — especially: **no warm-cream
   background**, one accent (sage), cards never over ~16px radius, no
   border+heavy-shadow ghost cards, reading prose in the serif.
5. If a product needs its own colors (an app's charts, a map's phases), keep
   those in a small local `tokens.local.css` layered after the core — do not
   add them to the shared `assets/tokens.css`.

## Consuming the tokens per stack

- **Plain CSS** (dobby-dashboard, ~/GitHub/agents/dashboard): copy `tokens.css` in and
  `@import` / link it before app styles. Tokens cascade as-is.
- **Tailwind** (blog/adithyan.io): import `tokens.css` for the variable
  definitions, then point the Tailwind theme at the variables
  (e.g. `colors: { bg: 'var(--bg)', accent: 'var(--accent)' }`). Swap the body
  font to Newsreader for reading + Inter for UI, and replace any cream
  background with `--bg`.

The `~/GitHub/adi-design` repo is the canon; this skill is a vendored extract of
it. Authoring happens in the Claude Design project, which exports into that repo —
see the note in `references/design-language.md`.

## Scope — identity, craft, voice

Three skills shape Adi's work, split by axis. Keeping each lesson in the skill
that owns its axis is what stops any one from bloating into a catch-all:

- **adi-design — identity (the _look_).** Palette, the three fonts, space/shape,
  the functional-accent and no-cream rules. The values + the why.
- **impeccable — craft (the _method_).** Contrast/motion rigor, anti-slop,
  layout-pattern selection (master-detail vs table vs cards), build/critique/polish.
  Deliberately no house style of its own.
- **adi-writing — voice (the _words_).** How copy and prose sound like Adi.

On Adi's apps, where they overlap, **identity wins on look.** File each new lesson
where it belongs: a _look_ rule → here; a _method_ rule → impeccable; a _voice_
rule → adi-writing; a one-app implementation detail → that app's local docs or
`tokens.local.css`. Do not fold craft, content, or app-specifics into this skill.

## With impeccable (the craft companion)

`impeccable` is a general frontend-craft engine — contrast, motion, anti-slop
bans, build/critique/polish workflows. It has rigor but deliberately no house
style. This skill is the missing half: the **identity**. They compose on
different axes — impeccable is the *how* (method), adi-design is the *what*
(Adi's look) — so use them together, not instead of each other.

When running impeccable (or any craft pass) on one of Adi's apps
(dobby-dashboard, blog/adithyan.io, ~/GitHub/agents dashboard, or a new personal app):

- Treat `assets/tokens.css` as **committed brand colors**. Do NOT run
  impeccable's palette-generation / brand-seed step — the identity is already
  decided. (impeccable's own setup says to skip palette generation when
  committed colors exist; identity-preservation wins.)
- Apply impeccable's craft rigor *on top of* these tokens, never in place of
  them. Sage stays the one accent; no new palette, no cream background.
- The handshake is the project's own tokens + `DESIGN.md`: keep those pointing
  at this skill so impeccable picks up the identity automatically.

In short: **impeccable for craft, adi-design for identity. Where they meet on
Adi's apps, adi-design wins on look.**

## Evolving the language

The aesthetic changes in the **canon**, not here: author it in the Claude Design
project, export into `~/GitHub/adi-design`, bump `system/VERSION`. Then keep this
skill in step — refresh `assets/tokens.css` from the repo's `system/styles.css`
and update the rationale in `references/design-language.md` to match. Never edit a
token value only in this vendored copy; the repo is the one source.
