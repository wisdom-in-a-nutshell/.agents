---
name: dobby-mail
description: "Operate Dobby's Gmail-only mail client: search/read Gmail, fetch message bodies, use a small local Gmail cache, poll Gmail history, create drafts/replies, send only with explicit confirmation, and perform safe Gmail mutations."
---

# Dobby Mail

Email operations go through the skill-bundled CLI:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail
```

The CLI is **Gmail API only**. It is JSON-first, non-interactive, cache-aware,
and permission-safe. Apple Mail / EMLX / Mail.app automation is no longer part
of this client; if a future task genuinely needs non-Gmail local mail state, use
a separate explicit tool rather than reintroducing it here.

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

## Cache model

The cache is a small SQLite state store, not a full local mailbox clone.

Default path:

```text
~/.cache/dobby-mail/cache.sqlite
```

Override with `DOBBY_MAIL_CACHE_PATH` or `--cache-path`.

It stores:

- Gmail `history_id` sync cursor per account.
- Metadata for messages Dobby has searched/fetched.
- Body text / attachment metadata only for messages Dobby has explicitly read,
  synced with `--include-body`, exported, or attachment-inspected.

Why it exists:

- Enables reliable 15-minute polling with `sync` / `history` without losing the
  last cursor.
- Dedupes repeated “what changed?” checks.
- Avoids refetching the same body during follow-up work in the same day/thread.
- Gives Dobby a resumable local state surface for monitors and inbox triage.

When it is not needed:

- One-off `search`, `recent`, or `get` commands can run stateless with
  `--no-cache`.
- Historical search should still start with Gmail search; only cache matched
  messages that Dobby actually needs.

Use `get --refresh` to bypass a cached body and refetch from Gmail. Use
`cache-status` to inspect the local state.

## Common commands

```bash
# health / auth
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail doctor --check-gmail-api --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-auth --account adithyan@wisdominanutshell.academy

# cache / polling
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail cache-status --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail sync --reset --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail sync --fetch --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail history --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail history --since HISTORY_ID --fetch --no-input

# Gmail reads
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail recent --limit 20 --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail search --query "invoice newer_than:30d" --limit 20 --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail get --id gmail-message:MESSAGE_ID --max-body-chars 12000 --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail get --id gmail-message:MESSAGE_ID --refresh --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail export --id gmail-message:MESSAGE_ID --out-dir /tmp/mail-export --raw --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail attachments --id gmail-message:MESSAGE_ID --out-dir /tmp/mail-attachments --no-input

# draft-first writes
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft --to person@example.com --subject "Subject" --body-file /tmp/body.txt --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft --to person@example.com --subject "Subject" --body-file /tmp/body.txt --attach /tmp/report.pdf --dry-run --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail draft-reply --id gmail-message:MESSAGE_ID --body-file /tmp/body.txt --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail send --to person@example.com --subject "Subject" --body-file /tmp/body.txt --attach /tmp/report.pdf --confirm-send --dry-run --no-input

# confirmed Gmail mutations
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-archive --gmail-id gmail-message:abc123 --confirm-mutate --dry-run --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-trash --gmail-id gmail-message:abc123 --confirm-mutate --dry-run --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-mark-read --gmail-id gmail-message:abc123 --confirm-mutate --dry-run --no-input
$HOME/GitHub/agents/skills-source/owned/dobby-mail/scripts/dobby-mail gmail-filter --from noise@example.com --action trash --confirm-mutate --dry-run --no-input
```

## Gmail read/search behavior

- `search --query` uses Gmail query syntax.
- `recent` defaults to `in:inbox` and supports `--label`.
- `get` fetches the full Gmail message body and attachment metadata, then caches
  the fetched body unless `--no-cache` is passed.
- Search/recent fetch metadata/snippets only; fetch full bodies with `get`.
- For heavy historical work, search Gmail first, then fetch/cache only matched
  messages as needed. Do not bulk-fetch full bodies without throttling.

## Gmail history / polling

Use `sync` for the normal cached polling path:

1. `sync --reset` creates a baseline and stores Gmail's current `history_id`.
2. Every polling interval, run `sync --fetch`.
3. Add `--include-body` only when body text is needed for automation.
4. If Gmail says the cursor is stale, run `sync --reset` and do a bounded
   resync/search for the gap.

Use `history` directly when a caller wants stateless control over cursor storage.

## Gmail writes and mutations

Use Gmail API so headless Dobby does not depend on local app sync.

- `draft` and `draft-reply` create unsent Gmail drafts.
- `send` requires explicit user approval plus `--confirm-send`.
- `draft`, `draft-reply`, and `send` support outbound attachments with
  repeatable or comma-separated `--attach PATH`; `--dry-run` reports attachment
  metadata without creating/sending anything.
- Gmail mutation/filter commands require `--confirm-mutate`; use `--dry-run`
  first for anything non-trivial.
- Gmail trash is reversible; permanent delete is intentionally not exposed.

## Safety rules

- Prefer drafts. Do not send mail unless Adi explicitly approves that exact send
  in the current turn.
- Do not delete/archive/move/mark messages unless Adi explicitly approves that
  exact mailbox mutation in the current turn.
- Do not create Gmail filters unless Adi explicitly approves; dry-run first.
- `export` and `attachments` write only to caller-provided output directories.

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
bash $HOME/GitHub/agents/skills-source/owned/dobby-mail/tests/run.sh
RUN_LIVE=1 bash $HOME/GitHub/agents/skills-source/owned/dobby-mail/tests/run.sh
```
