---
name: contact-form-automation
description: Create or update contact forms for Ghost or Next.js sites using the WIN backend and Cloudflare Turnstile. Use when adding a contact page, wiring Turnstile (site key + secret), updating the backend allowlist/enforcement, or standardizing contact form markup across themes.
---

# Contact Form Automation

Use this skill to ship a working contact form backed by the WIN `/contact/form` endpoint with Turnstile required.

## Quick start

1) **Turnstile + backend**
- Follow `references/cloudflare.md` to add hostnames and fetch the site key + secret.
- Follow `references/backend.md` to add the origin to the allowlist and **always** enforce Turnstile.
- Use the env var list in `references/backend.md` (WIN `.env` / `.env.example`) and set
  `CONTACT_FORM_TURNSTILE_SECRET` in Azure App Service `aipodcasting`.

2) **Ghost**
- Copy `assets/ghost/page-contact.hbs` into the theme and hardcode the site key.
- Follow `references/ghost.md` to create the Ghost page and apply the template.

3) **Next.js (placeholder)**
- See `references/nextjs.md` for the placeholder steps to implement later.

## Defaults (AIP)
- Backend endpoint: `https://aipodcasting-hzbxdueeg4eeatgh.eastus-01.azurewebsites.net/contact/form`
- Turnstile: **always required** for allowed origins.

## Resources
- `assets/ghost/page-contact.hbs`
- `references/cloudflare.md`
- `references/backend.md`
- `references/ghost.md`
- `references/nextjs.md`
