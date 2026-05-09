# Dobby memory commands

Use the Dobby memory CLI for deterministic reads and append-only writes. Use
`dobby-shelf` for Shelf work and `dobby-calendar` for calendar work.

## Read

```bash
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>.<file>
```

`area.<name>` concatenates all Markdown files in `memory/areas/<name>/`.
`area.<name>.<file>` reads one file without the `.md` suffix.

## Append

```bash
echo "- 2026-05-09 — event" | \
  $HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory write \
  --section area.<name>.log \
  --message "short label"
```

Use append for logs. Do not use append for canonical section rewrites.

## Direct-edit fallback

Use direct file edits for:

- rewriting sections in `memory/now.md` or area canon files
- editing `soul.md`
- creating new journal files
- surgical cleanup/consolidation

Read before writing and preserve continuity when removing or consolidating text.

## Tests

```bash
bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh
```

## Diff/history

```bash
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "24 hours ago"
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "1 week ago"
```
