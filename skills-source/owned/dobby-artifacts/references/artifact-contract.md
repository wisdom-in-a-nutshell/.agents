# Dobby Artifact Contract

Use this reference when creating, promoting, or restructuring a durable Dobby artifact.

## Definition

A Dobby artifact is a visible, self-contained working surface that lives inside a person workspace and can be opened by both the user and Dobby. It may be static or interactive. It may contain its own data files, styling, scripts, and assets.

The stable unit is the artifact folder, not one particular file format.

## Canonical Location

```text
memory/areas/<area>/artifacts/<slug>/
```

Examples:

```text
memory/areas/career/artifacts/skills-worksheet/
memory/areas/health/artifacts/supplement-tracker/
memory/areas/family/artifacts/apartment-sale-board/
```

Choose:

- `<area>` from the workspace's existing `memory/areas/` folders when possible.
- `<slug>` as lowercase hyphen-case, stable, and content-specific.

## Minimum Files

```text
artifact.json
index.html
```

Optional files:

```text
data/<source>.json
style.css
script.js
assets/<files>
```

Avoid scattering one artifact's files outside its folder unless there is a documented shared asset or engine-level reason.

## Manifest Shape

Use `artifact.json` as the dashboard/discovery manifest. Recommended shape:

```json
{
  "schemaVersion": 1,
  "kind": "dobby-artifact",
  "title": "Skills Worksheet",
  "description": "Career skills worksheet for exploring strengths, evidence, and patterns.",
  "area": "career",
  "slug": "skills-worksheet",
  "entry": "index.html",
  "pinned": true,
  "updatedAt": "2026-06-24T17:31:00+02:00",
  "source": {
    "kind": "json",
    "path": "data/worksheet.json"
  },
  "tags": ["career", "worksheet"]
}
```

Rules:

- `schemaVersion`, `kind`, `title`, `area`, `slug`, and `entry` should be present.
- `kind` should be `dobby-artifact`.
- `entry` should be a relative path inside the artifact folder.
- `pinned: true` means the artifact is important enough for a dashboard home surface if supported.
- `source` is optional but useful when the artifact has a clear data source.
- Do not put secrets or external credentials in the manifest.

## Source Patterns

Pick one real source of truth. The visible page may render from that source, but should not silently diverge.

### JSON + HTML

Best default for structured artifacts. Use when rows, cards, sections, or state need to be updated by Dobby.

```text
data/worksheet.json
index.html
```

### HTML-only

Use for small, static, polished surfaces where separate data would add friction.

### Markdown + HTML

Use when prose is the source and HTML is a reading/interaction layer.

### CSV + HTML

Use only when simple tabular editing or import/export matters.

### XLSX

Use only when native spreadsheet behavior is genuinely needed. If Excel is only a carry-over from a previous draft, prefer converting to JSON/HTML so the artifact is self-contained and easier for Dobby to update.

## Dashboard Serving Contract

The shared dashboard may serve artifacts at:

```text
/artifacts/<area>/<slug>/
```

Expected behavior:

- List artifacts by reading `memory/areas/*/artifacts/*/artifact.json`.
- Serve only files inside artifact folders that have a valid `artifact.json`.
- Resolve `entry` for the artifact root.
- Never expose arbitrary workspace paths.
- Keep serving and UI behavior in `~/GitHub/dobby-engine`, not in `adi` or `angie`.

## Area Indexing

If the workspace uses `memory/areas/<area>/area.json` to declare data directories, add `artifacts` only if the body map or existing area convention requires it.

Do not duplicate detailed artifact contents inside `area.json`; keep discovery in each artifact's `artifact.json`.

## Validation

After artifact changes, run the touched workspace's fast check:

```bash
cd ~/GitHub/angie && scripts/check-fast.sh
cd ~/GitHub/adi && scripts/check-fast.sh
```

After shared dashboard or engine changes, run:

```bash
cd ~/GitHub/dobby-engine && scripts/check-fast.sh
```

If dashboard serving changed, also smoke-test a real artifact URL from one workspace.
