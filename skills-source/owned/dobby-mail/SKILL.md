---
name: dobby-mail
description: "Operate Dobby's Gmail-first mail client: search/read recent mail, fetch message bodies, poll Gmail history, create drafts, create reply drafts, and perform safe Gmail mutations. Apple Mail/EMLX backends are legacy explicit-only escape hatches, not the primary path."
---

# Dobby Mail

Email operations go through the skill-bundled CLI:

```bash
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail
```

The CLI is **Gmail API–first** for reads, search, polling, drafts, sends, and
Gmail-native mutations. It is JSON-first, non-interactive, and permission-safe.

Apple Mail `Envelope Index` / `.emlx` and Mail.app automation are deprecated
legacy backends. Use them only when the user explicitly needs Apple Mail / iCloud
/ selected-message behavior. Do not use Apple Mail as the normal fallback for
Gmail/Workspace mail.

## Identity and secrets

Run it from a Dobby workspace root when possible. Workspace identity is explicit:

- `DOBBY_MAIL_DEFAULT_ACCOUNT` is required for Gmail API reads and writes unless
  `--account` is passed.
- `DOBBY_MAIL_DEFAULT_FROM` is required for draft/send identity when `--sender`
  is not passed.
- OAuth client JSON and refresh tokens are canonical in Azure Key Vault and
  materialized locally with:

```bash
~/GitHub/scripts/sync/keyvault-sync-gmail-secrets.sh --apply
```

Local files default to `~/.secrets/gmail/client_secret.json` and
`~/.secrets/gmail/tokens.json` (overridable by `DOBBY_GMAIL_OAUTH_CLIENT_FILE`
and `DOBBY_GMAIL_TOKENS_FILE`). Do not pass OAuth secrets or refresh tokens via
flags or ordinary environment variables.

## Common commands

```bash
# health / auth
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail doctor --check-gmail-api --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-auth --account adithyan@wisdominanutshell.academy

# Gmail reads
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail recent --limit 20 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail search --query "invoice newer_than:30d" --limit 20 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail get --id gmail-message:MESSAGE_ID --max-body-chars 12000 --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail export --id gmail-message:MESSAGE_ID --out-dir /tmp/mail-export --raw --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail attachments --id gmail-message:MESSAGE_ID --out-dir /tmp/mail-attachments --no-input

# 15-minute poll/sync primitive
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail history --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail history --since HISTORY_ID --fetch --no-input

# draft-first writes
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft --to person@example.com --subject "Subject" --body-file /tmp/body.txt --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft-reply --id gmail-message:MESSAGE_ID --body-file /tmp/body.txt --no-input

# confirmed Gmail mutations
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-archive --gmail-id gmail-message:abc123 --confirm-mutate --dry-run --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-trash --gmail-id gmail-message:abc123 --confirm-mutate --dry-run --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-mark-read --gmail-id gmail-message:abc123 --confirm-mutate --dry-run --no-input
$HOME/.agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-filter --from noise@example.com --action trash --confirm-mutate --dry-run --no-input
```

## Backend rules

- Default read backend is `--backend auto`, which means **Gmail API**.
- `--backend gmail-api` is the explicit primary backend.
- `--backend fast` and `--backend mail-app` are deprecated Apple legacy
  backends. They emit `W_LEGACY_APPLE_BACKEND` warnings and should only be used
  for Apple Mail / iCloud / local selected-message edge cases.
- `--all-accounts` is not supported for Gmail API reads. Use one account at a
  time. Multi-account aggregation belongs in a higher-level Dobby coordinator or
  cache, not inside a single ambiguous read command.

## Gmail read/search behavior

- `search --query` uses Gmail query syntax.
- `recent` defaults to `in:inbox` and supports `--label`.
- `get` fetches the full Gmail message body and attachment metadata.
- Search/recent fetch metadata/snippets only; fetch full bodies with `get`.
- For heavy historical work, search Gmail first, then cache/fetch only matched
  messages as needed. Do not bulk-fetch full bodies without throttling.

## Gmail history / polling

Use `history` for lightweight polling:

1. Call `history` with no `--since` to get a baseline `history_id`.
2. Store that ID in the caller/cache.
3. Every polling interval, call `history --since HISTORY_ID`.
4. Use `--fetch` to fetch changed message metadata; add `--include-body` only
   when body text is needed.
5. If Gmail returns a stale-history error, do a bounded resync and store a new
   baseline.

For a local Dobby client, 15-minute polling via Gmail history is safe and far
cleaner than Apple Mail sync/EMLX hydration.

## Gmail API writes and mutations

Use Gmail API so headless Dobby does not wake Mail.app or fight Apple Mail sync.

- `draft`, `draft-reply`, and `send` accept `--write-backend auto|gmail-api|mail-app`.
- `auto` uses Gmail API when `DOBBY_MAIL_DEFAULT_ACCOUNT` is configured.
- `send` requires explicit user approval plus `--confirm-send`.
- Gmail mutation/filter commands require `--confirm-mutate`; use `--dry-run`
  first for anything non-trivial.
- Gmail trash is reversible; permanent delete is intentionally not exposed.

## Safety rules

- Prefer drafts. Do not send mail unless Adi explicitly approves that exact send
  in the current turn.
- Do not delete/archive/move/mark messages unless Adi explicitly approves that
  exact mailbox mutation in the current turn.
- Do not create Gmail filters unless Adi explicitly approves; dry-run first.
- `export` and `attachments` support Gmail message ids and write only to caller-provided output dirs. Legacy `fast:<rowid>` ids remain explicit Apple-only escape hatches.

## Contract

- JSON envelope by default: `schema_version`, `command`, `status`, `data`,
  `error`, `meta`.
- Supports `--plain` only for operator inspection.
- Supports `--no-input`; normal commands never prompt.
- Primary output stays on stdout. Warnings/diagnostics go to stderr.
- Stable errors use `error.code`, `message`, `hint`, and mapped exit codes.
- No secret values are accepted via flags or ordinary environment variables.

## Testing

```bash
bash $HOME/.agents/skills-source/owned/dobby-mail/tests/run.sh
RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby-mail/tests/run.sh
```
