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

If an older setup still has `~/.secrets/linkedin/personal-posting.tokens.json`, the CLI falls back to it automatically.

Generated env file after machine-secret sync:

```bash
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
```

The script defaults the redirect URI and scope, so those do not need to be stored as secrets.

## One-time LinkedIn app setup

1. Go to the LinkedIn Developer Portal and create an app.
2. Under the app's Auth settings, add this redirect URL exactly:
   - `http://127.0.0.1:8765/callback`
3. Under Products, add:
   - `Share on LinkedIn`
4. If you want the script to resolve your user identifier through OIDC as part of the same flow, also add:
   - `Sign In with LinkedIn using OpenID Connect`
5. Store the Client ID and Client Secret in Key Vault under the `linkedin--...` family, then sync machine secrets

## Authorize locally

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize
```

What it does:
- opens the LinkedIn OAuth consent flow
- listens on the local callback URL
- exchanges the auth code for a token
- calls the LinkedIn userinfo endpoint
- stores the token JSON locally

## Confirm identity

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py whoami
```
