# Cloudflare Turnstile

## Create or update a Turnstile site
- Prefer **one Turnstile site** per brand and add multiple hostnames to it.
- Add hostnames without scheme (no `http://` or `https://`).

## Required outputs
- **Site key** (public) -> used in the front-end template.
- **Secret key** (private) -> stored as `CONTACT_FORM_TURNSTILE_SECRET` in Azure.

## Defaults (AIP)
- The site key can be hardcoded in the template.
- If you want to keep it in env for templating, use a local-only var such as
  `CONTACT_FORM_TURNSTILE_SITE_KEY` and replace the placeholder in the template.
