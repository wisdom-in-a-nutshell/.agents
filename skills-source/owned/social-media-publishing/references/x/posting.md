# X posting

Use this when Adi wants to publish personal posts to X from local tooling.

If X is already configured on this machine, start here.
If not, use `references/x/auth.md` once and then come back.

On a fresh boot, run `status` first.

## What this covers

Current minimal workflow:
- runtime/auth inspection via `status`
- text posting via `post`
- machine-readable CLI output for agent use

This first version does not yet cover image uploads, threads, replies, scheduling, or analytics.

## Local CLI

Script:
- `scripts/x/cli.py`

Related references:
- `references/x/auth.md` only if setup is needed
- `references/x/copy.md` for tone/defaults

## Interface contract

The X CLI follows the same machine-first pattern:
- JSON is the default output contract
- `--plain` is only for lighter operator inspection
- `--no-input` disables future interactive behavior
- non-zero exit codes are classified by failure type

### First command on a fresh boot

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/x/cli.py status
```

What it surfaces:
- resolved env file
- whether the required OAuth 1.0a credentials are present
- whether a live `/2/users/me` probe works
- which X account is connected if the probe succeeds

### Dry-run a post

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post \
  --text-file /abs/path/body.txt \
  --dry-run
```

### Publish for real

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post \
  --text-file /abs/path/body.txt
```

## What the client still needs from the user

Before posting will work, the machine needs X OAuth 1.0a user-context credentials in `~/.secrets/x/env`:
- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

If those are missing, use `references/x/auth.md` and then come back to `status`.

## Official docs used

- X API quickstart for manage posts (`POST /2/tweets`): https://docs.x.com/x-api/posts/manage-tweets/quickstart
- OAuth 1.0a overview: https://docs.x.com/fundamentals/authentication/oauth-1-0a/overview
- Authenticated user lookup quickstart (`GET /2/users/me`): https://docs.x.com/x-api/users/lookup/quickstart/authenticated-lookup
