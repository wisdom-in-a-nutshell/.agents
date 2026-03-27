# X auth setup

Use this only when X is not already configured on the current machine.

## Recommended auth path

For Adi's personal posting workflow, use X API v2 with OAuth 1.0a user-context credentials.

Store these in the machine-local shared lane:
- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

Recommended env file:
- `~/.secrets/x/env`

Example shape:

```bash
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_TOKEN_SECRET=...
```

## Why this path

For personal posting, OAuth 1.0a user-context credentials are the cleanest low-maintenance setup.

Compared with LinkedIn:
- no 60-day access-token churn in the same way
- simpler machine-local setup once the keys and tokens are generated

## Official docs used

- OAuth 1.0a overview: https://docs.x.com/fundamentals/authentication/oauth-1-0a/overview
- Obtaining user access tokens: https://docs.x.com/resources/fundamentals/authentication/oauth-1-0a/obtaining-user-access-tokens
- Getting access: https://docs.x.com/x-api/getting-started/getting-access
