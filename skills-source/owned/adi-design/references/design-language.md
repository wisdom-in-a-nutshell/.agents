# Adi's design language

The aesthetic shared across Adi's apps. The tokens in `assets/tokens.css` are
the *values*; this file is the *why and how* — the part that keeps future work
recognizably his. When the tokens and this doc disagree, fix one to match the
other; they are meant to stay in lockstep.

## The feel

A calm reading room. Quiet, file-backed, unhurried. One cohesive language on
every surface. Warmth comes from a literary serif on reading prose, a sage
accent, an amber secondary, and generous spacing — never from a warm-tinted
background. Flat surfaces, hairline borders, no ghost-card shadows. Motion is
restrained and earns its place by signalling state, not decorating.

It should read as "a person made this with taste," not "an AI generated a
dashboard."

## Color

- **Background is a clean off-white**, whisper-tinted toward sage — `--bg`.
  Dark mode is a warm-neutral charcoal, not green, not pure black.
- **Sage is the single accent** (`--accent`): action, selection, focus, active
  state. One accent, used sparingly. Do not introduce a second "primary."
- **Amber is the secondary** (`--amber`): warmth, wellbeing, journal context.
- **Rose** (`--rose`) is rare — emphasis or a "needs a look" state only.
- Gray-on-tint is the most common contrast failure. Body text must clear
  4.5:1; if it's close, push toward `--text`, never toward `--faint`.

## Typography

- **Newsreader (serif)** for reading prose, page titles, and detail headings.
- **Inter (sans)** for all UI chrome, labels, metadata, controls.
- **System mono** for code and ids.
- Three families, hard cap. Hierarchy comes from scale + weight, not new fonts.
- Reading column caps at ~65–75ch. Reading line-height is generous
  (`--leading-read`).

## Space & shape

- Spacing rhythm: 4, 8, 12, 18, 28, 44 (`--space-*`). Vary it for rhythm; don't
  pad everything to one value.
- Radius: controls 10, cards/panels 14, large reading frames 18, pills round.
  **Cards never exceed ~16** — no 24/32/40px "insanely rounded" cards.
- Flat elevation. Hairline borders for structure. Never pair a 1px border with
  a ≥16px drop shadow (the ghost-card tell).

## Motion

- Restrained and state-only: hover, selection, overlay enter. Ease out
  (`--ease-out`), no bounce, no elastic.
- Every animation needs a `prefers-reduced-motion: reduce` path (usually a
  crossfade or instant state).

## Hard rules

Do:
- Start from `assets/tokens.css`. Reference tokens, not raw values.
- Use the serif for anything meant to be *read*; sans for anything meant to be
  *operated*.
- Keep one accent. Let amber/rose stay contextual.

Don't:
- **No warm cream / sand / paper / beige background.** This is the single most
  important rule and the most common drift. The whole warm near-white band
  reads as the AI default. Warmth lives in type and accent, never the bg.
- No second accent color competing with sage.
- No gradient text, no decorative glassmorphism, no side-stripe accent borders.
- No over-rounded cards, no ghost-card border+shadow combos.
- No em dashes in UI copy; no marketing-buzzword voice.

## Per-product notes

- **dobby-dashboard** — the reference implementation. Plain CSS, single
  `styles.css`, tokens already match this file. When the language evolves,
  evolve it here *and* in dobby together.
- **blog / adithyan.io** — Next.js + Tailwind. Currently on warm beige + Source
  Serif: the main thing to migrate. Map these tokens into the Tailwind theme
  (Tailwind reads CSS variables), swap Source Serif → Newsreader, kill the cream
  bg for `--bg`.
- **~/.agents/dashboard** — plain HTML/CSS, already oklch + Inter + a sage-family
  hue. Close already; align the accent (it skews teal ~175 → bring to sage 151)
  and add the serif reading layer where prose appears.

## On Claude Design (claude.ai/design)

Useful as a one-way *sketchpad*, not a sync partner. It links a repo for
component context (best fed by a real product like dobby, not a tokens-only
repo) and inherits a design system configured inside its own product — it does
not push back or stay in sync. Explore there freely, then bring changes back
and fold them into `assets/tokens.css` by hand. This skill remains canon.
