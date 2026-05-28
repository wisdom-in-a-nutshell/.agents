---
name: dobby-mail
description: "Operate Dobby's local mail client: Apple Mail fast/local reads and safe Gmail API writes. Use for checking recent mail, searching Apple Mail, reading a message, listing mailboxes/accounts, creating unsent email drafts, creating reply drafts, sending only with confirmation, and debugging Mail.app/Gmail write access."
---

# Dobby Mail

Email operations go through the skill-bundled CLI:

```bash
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail
```

The CLI is Apple Mail–centered for reads, Gmail API–centered for Gmail writes,
JSON-first, and permission-safe. It uses a fast read-only Apple Mail
`Envelope Index` + `.emlx` path when available and explicitly falls back to
Mail.app automation when allowed.
Fallbacks are reported on `stderr` and in JSON `data.warnings`.

Run it from a Dobby workspace root when possible. Workspace identity is explicit:

- `DOBBY_MAIL_DEFAULT_ACCOUNT` is required for ambiguous reads
  (`recent`, `search`, `get`, `mailboxes`, `export`, `attachments`,
  `draft-reply`). Use `--all-accounts` only when the user explicitly asks to
  read across every Apple Mail account.
- `DOBBY_MAIL_DEFAULT_FROM` is required for draft/send identity when `--sender`
  is not passed. Do not fall back from one variable to the other. For real
  Mail.app draft/send actions, the sender must be configured on the default
  Apple Mail account; fail fast rather than creating mail from the wrong
  account. For Gmail API writes, the default account is the authorized Gmail /
  Google Workspace account and `DOBBY_MAIL_DEFAULT_FROM` is the `From:` address
  or configured Gmail send-as alias.

## Common commands

```bash
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail doctor --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail doctor --check-mail-app --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail doctor --check-gmail-api --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail setup --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-auth --account adithyan@wisdominanutshell.academy
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail accounts --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail mailboxes --limit 50 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail recent --limit 20 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail search --query "invoice" --limit 20 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail get --id fast:123 --max-body-chars 12000 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail selected --limit 10 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail export --id fast:123 --out-dir /tmp/mail-export --raw --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail attachments --id fast:123 --out-dir /tmp/mail-attachments --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft --to person@example.com --subject "Subject" --body-file /tmp/body.txt --write-backend gmail-api --no-input
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

## Gmail API write backend

Use Gmail API for Gmail / Google Workspace writes so headless Dobby does not
wake Mail.app or fight Apple Mail draft UI/sync behavior.

- Read/search remains Apple Mail-only. Do not add a Gmail read fallback unless
  Adi explicitly asks for it.
- `draft`, `draft-reply`, and `send` accept `--write-backend auto|gmail-api|mail-app`.
- `auto` uses Gmail API when `DOBBY_MAIL_DEFAULT_ACCOUNT` is configured; if no
  default account exists, it explicitly warns and uses Mail.app.
- `--write-backend gmail-api` requires a one-time `gmail-auth` per account.
  Current auth intentionally requests broad Gmail scopes for future mail
  operations: full mailbox access (`https://mail.google.com/`) plus basic Gmail
  settings access for filters/blocking (`gmail.settings.basic`).
- OAuth client JSON and refresh tokens are canonical in Azure Key Vault and
  materialized locally with
  `~/GitHub/scripts/sync/keyvault-sync-gmail-secrets.sh --apply`.
  Local files default to `~/.secrets/gmail/client_secret.json` and
  `~/.secrets/gmail/tokens.json` (overridable by `DOBBY_GMAIL_OAUTH_CLIENT_FILE`
  and `DOBBY_GMAIL_TOKENS_FILE`). macOS Keychain may exist as an interactive
  auth cache, but it is not the canonical bootstrap source.
- Do not pass OAuth secrets or refresh tokens through flags or env vars.
- Gmail API returns a draft id but not a stable universal draft deep link. JSON
  includes `links.gmail_drafts` for opening Gmail Drafts and `links.mail`
  (`message://...`) for local Apple Mail after sync.

## Safety rules

- Prefer drafts. Gmail API drafts are true background writes. Mail.app drafts
  are **unsent background** Apple Mail drafts; they do not open compose windows.
  When Mail exposes a message id for the draft, JSON includes `draft.mail_url`
  and `draft.links.mail`; the client also tries to resolve the link from the
  local fast index after saving. Apple Mail may still briefly appear if macOS
  has to launch or wake Mail.app; use Gmail API writes for Gmail accounts when
  zero-UI/headless behavior matters.
- Do not send, delete, archive, move, or mark messages unless Adi explicitly
  approves that exact action in the current turn.
- `send` exists only for explicit approved sends and requires `--confirm-send`.
  Prefer creating a draft and asking Adi to inspect/send manually.
- `mark-read` and `flag` require `--confirm-mark` / `--confirm-flag`.
- `export` and `attachments` write files only to caller-provided output dirs.
- `draft-reply` v1 creates an addressed unsent draft from message metadata; it
  does not yet use Mail.app's native threaded reply command. Inspect the draft.

## Contract

- JSON envelope by default: `schema_version`, `command`, `status`, `data`,
  `error`, `meta`.
- Supports `--plain` only for operator inspection.
- Supports `--no-input`; normal commands never prompt.
- Primary output stays on stdout. Warnings/diagnostics go to stderr.
- No secret values are accepted via flags or environment variables.
  `DOBBY_MAIL_DEFAULT_ACCOUNT`, `DOBBY_MAIL_DEFAULT_FROM`, and
  `DOBBY_GMAIL_OAUTH_CLIENT_FILE` / `DOBBY_GMAIL_TOKENS_FILE` are non-secret
  identity/path configuration, not refresh-token storage. Gmail refresh tokens
  come from `~/.secrets/gmail/tokens.json` generated from Key Vault.

## Testing

```bash
bash $HOME/.agents/skills-source/owned/dobby-mail/tests/run.sh
RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby-mail/tests/run.sh
```
