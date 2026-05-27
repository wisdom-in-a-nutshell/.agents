---
name: dobby-mail
description: "Operate Dobby's local Apple Mail client for email reads and safe writes. Use for checking recent mail, searching Apple Mail, reading a message, listing mailboxes/accounts, creating unsent email drafts, creating reply drafts, and debugging Mail.app/local Mail access."
---

# Dobby Mail

Email operations go through the skill-bundled CLI:

```bash
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail
```

The CLI is Apple Mail–centered, local-first, JSON-first, and permission-safe.
It uses a fast read-only Apple Mail `Envelope Index` + `.emlx` path when
available and explicitly falls back to Mail.app automation when allowed.
Fallbacks are reported on `stderr` and in JSON `data.warnings`.

## Common commands

```bash
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail doctor --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail doctor --check-mail-app --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail accounts --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail mailboxes --limit 50 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail recent --limit 20 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail search --query "invoice" --limit 20 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail get --id fast:123 --max-body-chars 12000 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail selected --limit 10 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft --to person@example.com --subject "Subject" --body-file /tmp/body.txt --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft-reply --id fast:123 --body-file /tmp/body.txt --no-input
```

## Backend rules

- Default read backend is `--backend auto`: try fast local read, then explicitly
  fall back to Mail.app automation if fast access fails.
- Use `--backend fast --no-fallback` when you need deterministic local-index
  behavior and want failure instead of fallback.
- Use `--backend mail-app` when Full Disk Access is unavailable or when reading
  the currently selected messages.
- Fast backend may require Full Disk Access for the terminal/Codex host.
- Mail.app backend may require macOS Automation permission to control Mail.app.

## Safety rules

- Prefer drafts. `draft` and `draft-reply` create **unsent** Apple Mail drafts.
- Do not send, delete, archive, move, or mark messages unless Adi explicitly
  approves that exact action in the current turn.
- `send` exists only for explicit approved sends and requires `--confirm-send`.
  Prefer creating a draft and asking Adi to inspect/send manually.
- `draft-reply` v1 creates an addressed unsent draft from message metadata; it
  does not yet use Mail.app's native threaded reply command. Inspect the draft.

## Contract

- JSON envelope by default: `schema_version`, `command`, `status`, `data`,
  `error`, `meta`.
- Supports `--plain` only for operator inspection.
- Supports `--no-input`; normal commands never prompt.
- Primary output stays on stdout. Warnings/diagnostics go to stderr.
- No secrets are accepted via flags or environment variables.

## Testing

```bash
bash $HOME/.agents/skills-source/owned/dobby-mail/tests/run.sh
RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby-mail/tests/run.sh
```
