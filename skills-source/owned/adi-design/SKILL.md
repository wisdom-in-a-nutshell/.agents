---
name: adi-design
description: Apply Adi's personal design language so his apps look like one cohesive product. Use when building, restyling, or reviewing any UI for Adi's personal projects (dobby-dashboard, blog/adithyan.io, ~/.agents/dashboard) or a new personal app/page, including choosing colors, typography, spacing, radius, or motion, setting up a theme or design tokens, migrating a surface off a generic or warm-cream look, or judging whether a screen is on-brand. The aesthetic is clean off-white (never warm cream), oklch sage accent with amber secondary, Newsreader serif for reading and Inter for UI, flat hairline surfaces, and restrained state-only motion.
---

# Adi Design

A calm reading room: clean off-white, sage accent, serif for reading, flat
hairline surfaces, restrained motion. The goal is that every one of Adi's apps
feels like one product made by one person with taste.

## Flow

1. Read `references/design-language.md` — the aesthetic, the rules, the
   do's/don'ts, and the per-product notes. This is the part that keeps work
   recognizably Adi's.
2. Use `assets/tokens.css` as the source of truth for values. Reference tokens
   (`var(--accent)`, `--space-lg`), never raw hex/oklch literals.
3. Wire the tokens into the target the way that stack consumes them (below).
4. Apply, then check against the hard rules — especially: **no warm-cream
   background**, one accent (sage), cards never over ~16px radius, no
   border+heavy-shadow ghost cards, reading prose in the serif.
5. If a product needs its own colors (an app's charts, a map's phases), keep
   those in a small local `tokens.local.css` layered after the core — do not
   add them to the shared `assets/tokens.css`.

## Consuming the tokens per stack

- **Plain CSS** (dobby-dashboard, ~/.agents/dashboard): copy `tokens.css` in and
  `@import` / link it before app styles. Tokens cascade as-is.
- **Tailwind** (blog/adithyan.io): import `tokens.css` for the variable
  definitions, then point the Tailwind theme at the variables
  (e.g. `colors: { bg: 'var(--bg)', accent: 'var(--accent)' }`). Swap the body
  font to Newsreader for reading + Inter for UI, and replace any cream
  background with `--bg`.

This skill is canon. Tools like claude.ai/design are sketchpads to explore in,
then bring changes back here — see the note in `references/design-language.md`.

## With impeccable (the craft companion)

`impeccable` is a general frontend-craft engine — contrast, motion, anti-slop
bans, build/critique/polish workflows. It has rigor but deliberately no house
style. This skill is the missing half: the **identity**. They compose on
different axes — impeccable is the *how* (method), adi-design is the *what*
(Adi's look) — so use them together, not instead of each other.

When running impeccable (or any craft pass) on one of Adi's apps
(dobby-dashboard, blog/adithyan.io, ~/.agents dashboard, or a new personal app):

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

When the aesthetic changes, change it in **two places together**: the value in
`assets/tokens.css` and the rationale in `references/design-language.md`. Keep
dobby-dashboard (the reference implementation) in step. Full token extraction
from dobby can deepen over time; the current set is the shared core.
