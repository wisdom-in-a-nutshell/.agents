# Adi's design language

The aesthetic shared across Adi's apps. The tokens in `assets/tokens.css` are
the *values*; this file is the *why and how* — the part that keeps future work
recognizably his. When the tokens and this doc disagree, fix one to match the
other; they are meant to stay in lockstep.

**What lives here vs local:** this file holds the *universal* identity — the rules
that apply to every app. Anything specific to one app's function or data (a
dashboard's chart palette, an internal tool's layout, a map's phase colors) stays
in that app's local `tokens.local.css` or docs, never here.

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
- **The accent is functional, never decorative.** Sage only marks things you can
  act on or that carry state — links, active item, focus, selection. No
  accent-colored dots, bullets, flourishes, or wordmark marks. If a spot of
  accent isn't backed by action or state, it's ornament; cut it. (Same logic as
  the motion rule — it earns its place by signalling, not decorating. Ornament
  you have to justify usually wants to go.)
- **Amber is the secondary** (`--amber`): warmth, wellbeing, journal context.
- **Rose** (`--rose`) is rare — emphasis or a "needs a look" state only.
- Gray-on-tint is the most common contrast failure — and *meta* text (dates,
  captions, small labels) is where it hides. All text must clear 4.5:1, meta
  included. The trap is hard-coding a faint neutral (e.g. `neutral-400`) to make
  meta read "quiet"; reach for the muted token instead, which is tuned to pass.
  If a value is close, push toward `--text`, never toward `--faint`.
- **Colored text uses the ink depth, not the fill.** Sage, rose, and amber as
  *text* (links, errors, labels) — or as a button fill behind white text — must
  clear 4.5:1, so use the `-ink` variant (`--accent-ink`, `--rose-ink`,
  `--amber-ink`); they are tuned to pass. The base `--accent` / `--rose` /
  `--amber` are for fills, large non-text accents, hairlines, soft backgrounds,
  and state behind dark text — they do NOT clear AA as small text. In the
  Tailwind/shadcn apps (blog, adithyan.io, the AIP site) where one `--primary`
  token does both jobs, set `--primary` to the ink-depth sage, not the lighter
  fill (the canonical `135 25% 41%` is ~0.3 under; `137 30% 36%` clears it).

## Typography

- **Newsreader (serif)** for reading prose, page titles, and detail headings.
- **Inter (sans)** for all UI chrome, labels, metadata, controls.
- **System mono** for code and ids.
- Three families, hard cap. Hierarchy comes from scale + weight, not new fonts.
- Reading column caps at ~65–75ch. Reading line-height is generous
  (`--leading-read`).

## Imagery

Photos and illustrations are *content*, not chrome — the one-accent rule governs
the UI around an image, not the image itself. Let a real photo be honestly
full-color; don't desaturate it to grayscale or duotone it to "match" the
palette (it reads cold, and grayscale-on-hover reveals are invisible on touch).
The warmth of a real face or scene does the same job amber does elsewhere. Crop
to the subject on purpose — position the crop on the face/subject, not the
default center — so nothing important is clipped.

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
- Keep every interactive element keyboard-operable with a visible focus ring
  (use `--focus-ring`) and a reduced-motion path. Accessibility is universal, not
  a per-app concern — it lives here, not in product docs.

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
  `styles.css`, tokens already match this file (including the `--accent` /
  `--accent-ink` split). When the language evolves, evolve it here *and* in dobby
  together. Repo pointer: `docs/references/design-system.md`; the local CSS classes
  and component vocabulary live in `docs/references/ui-system.md` (implementation,
  not canon).
- **blog / adithyan.io** — static Astro + Tailwind (shadcn HSL token system,
  class-based dark). The shadcn tokens in `src/styles/global.css` (`:root` + `.dark`)
  carry the adi-design palette as HSL conversions of the canonical oklch values
  (token *names* kept so components + opacity modifiers still work); `--primary`
  and `--ring` are sage, `--destructive` is rose. Fonts are Newsreader + Inter
  (self-hosted via `@fontsource-variable/*`, not `next/font`). The warm cream/beige
  is gone (bg, dark bg, prose ink, selection, theme-color, resume dots).
- **aipodcasting-website** (aipodcast.ing) — static Astro + Tailwind, same shadcn
  HSL token system as the blog (class-based dark). Tokens in `src/styles/global.css`
  carry the palette as HSL conversions; `--primary` and `--ring` are the **ink-depth**
  sage (`137 30% 36%`, AA-safe as a button fill behind white text and as link text),
  `--destructive` is the AA-safe rose. Wider than the blog: `max-w-site` (1040px) for
  grids/stat rows, `max-w-readable` (720px) for text pages. Repo pointer:
  `docs/references/design-system.md`.
- **~/GitHub/agents/dashboard** — React + Vite + TS (same stack as dobby). Source in
  `~/GitHub/agents/dashboard-app`, built into `~/GitHub/agents/dashboard`, served by the
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
