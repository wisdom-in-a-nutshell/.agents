# Adi's design language

The aesthetic shared across Adi's apps. The tokens in `assets/tokens.css` are
the *values*; this file is the *why and how* — the part that keeps future work
recognizably his. When the tokens and this doc disagree, fix one to match the
other; they are meant to stay in lockstep.

## The feeling (the north star)

Walking a forest trail mid-morning. The canopy is green but not dense, and soft
golden sunlight streams through it in patches: warm, never glaring. The air is
fresh. It is calm, and the calm makes room to think. That green-and-gold
warmth, dappled light through leaves, is the feeling every surface should give.
Dobby-dashboard already hits it; everything else should feel like the same walk.

How the tokens carry it:

- **Sage** (`--accent`) is the green: the canopy, the leaves, the cool living
  part.
- **Amber** (`--amber`) is the golden light breaking through. Warmth used
  sparingly, the way sun falls in patches, not a flood.
- **The off-white** (`--bg`) is fresh open air and light: cool-fresh, faintly
  green-tinted, NOT cream. Cream is stuffy indoor warmth; we want outdoor
  freshness with warm light *in* it.
- **Space and restraint** are the calm: generous spacing, flat surfaces, quiet
  motion. Room to breathe and think.

The trap: chasing "warm" by warming the background toward cream. That kills the
freshness and turns a forest morning into a beige room. The warmth must come
from the golden light (amber) and the serif, laid over fresh green-tinted light,
never from a warm background. This is *why* the no-cream rule exists, not just a
ban.

It should read as "a person made this with taste," not "an AI generated a
dashboard."

## The make-up

Quiet, file-backed, unhurried. One cohesive language on every surface. Flat
surfaces, hairline borders, no ghost-card shadows. Motion is restrained and
earns its place by signalling state, not decorating.

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
- **~/.agents/dashboard** — React + Vite + TS (same stack as dobby). Source in
  `~/.agents/dashboard-app`, built into `~/.agents/dashboard`, served by the
  Python control-plane engine at `/dashboard/`. Consumes the canonical
  `tokens.css` (copied to `src/`) plus a small `tokens.local.css` for its
  scope-global / scope-local tokens (scope-local *is* the sage accent; scope-global
  *is* amber/gold — the base kit as the golden light through the grove, the brand's
  own two colors, not a foreign accent; alerts move to rose). Titles
  are Newsreader; surfaces are flat hairline; the old teal accent is gone. Keep
  the Python data engine as the single source of truth; the dashboard is UI only.

## On Claude Design (claude.ai/design)

Useful as a one-way *sketchpad*, not a sync partner. It links a repo for
component context (best fed by a real product like dobby, not a tokens-only
repo) and inherits a design system configured inside its own product — it does
not push back or stay in sync. Explore there freely, then bring changes back
and fold them into `assets/tokens.css` by hand. This skill remains canon.
