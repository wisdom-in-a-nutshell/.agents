# LinkedIn auth setup

Use this only when LinkedIn is not already authenticated on the current machine.

If posting already works, you do not need this file for normal use.

## What this covers

- LinkedIn app bootstrap
- machine-local secret storage
- local OAuth authorization
- token refresh via the saved token file

## Secret lane

Use the machine-local shared lane.

Do not put LinkedIn app secrets in a repo.

Store them under:
- `~/.secrets/linkedin/env`
- `~/.secrets/linkedin/posting.tokens.json`

Generated env file after machine-secret sync:

```bash
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
LINKEDIN_APP_ID=...
LINKEDIN_REDIRECT_URI=...
LINKEDIN_SCOPE=...
```

The generated config is Community Management-first. Keep app id, redirect URI, and scope in the machine-secret mapping too so a future sync cannot silently drop the approved app context.

## App credentials vs user OAuth

There are two separate auth layers:

1. `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` identify the LinkedIn app. These are stable app credentials and are generated from the local canonical store into `~/.secrets/linkedin/env`.
2. `posting.tokens.json` is Adi's user OAuth authorization. This is the permission to post as Adi's LinkedIn profile.

On Adi's own encrypted Macs, the current convenience setup shares the OAuth token through Syncthing:

```bash
cd ~/GitHub/scripts
./setup/social/link-shared-linkedin-token.sh --apply
```

That links:

```text
~/.secrets/linkedin/posting.tokens.json
  -> ~/Syncthing/AppConfigs/LinkedIn/posting.tokens.json
```

This is intentionally separate from the canonical static-secret store because it is mutable runtime session state. Do not use this shared-token setup on temporary, shared, or cloud machines.

## One-time LinkedIn app setup

1. Go to the LinkedIn Developer Portal and create an app.
2. Under the app's Auth settings, add this redirect URL exactly:
   - `http://127.0.0.1:18965/callback`
   - This uses a high, LinkedIn-specific callback port to avoid the local dashboard/service ports tracked in `~/GitHub/agents` and `~/GitHub/scripts`, such as `8765` (agent dashboard), `8766` (Adi Dobby dashboard), and `8767` (Angie Dobby dashboard).
3. Under Products, use the approved current app with:
   - `Community Management API`
4. Store the app config in the local canonical store under the `linkedin--...` family, then sync machine secrets:
   - `linkedin--client-id`
   - `linkedin--client-secret`
   - `linkedin--app-id`
   - `linkedin--redirect-uri`
   - `linkedin--scope`
5. Do not keep a second LinkedIn app or legacy token fallback in the local tooling unless Adi explicitly asks to restore it.

## Authorize locally

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize
```

What it does:
- opens the LinkedIn OAuth consent flow
- listens on the local callback URL
- exchanges the auth code for a token
- resolves Adi's member URN through OIDC `/userinfo` when available, otherwise through LinkedIn `/v2/me` with `r_basicprofile`
- stores the token JSON locally

For the approved Community Management app, prefer:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize --scope-preset community
```

Then verify:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py community-status
```

## Confirm identity

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py whoami
```
