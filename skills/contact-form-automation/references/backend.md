# WIN Backend Contact Form

## Always enforce Turnstile
- Every allowed origin must also be in `TURNSTILE_REQUIRED_ORIGINS`.
- This ensures the backend rejects submissions without a Turnstile token.

## Files to update
- `services/notifications/contact_form.py`
  - Add new origin to `CONTACT_FORM_ROUTES`.
  - Add new origin to `TURNSTILE_REQUIRED_ORIGINS`.
  - Keep HTTPS only.

## Env vars (WIN repo: `.env` / `.env.example`)
Backend-required:
- `CONTACT_FORM_TOKEN` (Bearer token expected by `/contact/form`)
- `CONTACT_FORM_TURNSTILE_SECRET` (Turnstile secret key)
- `ACS_SMTP_PASS` (SMTP password for email notifications)

Turnstile provisioning (Cloudflare API):
- `CLOUDFLARE_TURNSTILE_API_TOKEN` (account-scoped Turnstile token)
- `CLOUDFLARE_ACCOUNT_ID`

Frontend convenience:
- `CONTACT_FORM_TURNSTILE_SITE_KEY` (optional; if not templating, hardcode in the theme)

## Endpoint
- `https://aipodcasting-hzbxdueeg4eeatgh.eastus-01.azurewebsites.net/contact/form`

## Notes
- Requests must include a valid `Origin` header.
- If Turnstile fails or secret is missing, the endpoint returns 403.
