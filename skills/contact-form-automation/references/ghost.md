# Ghost Theme + Page

## Theme changes
- Copy `assets/ghost/page-contact.hbs` into the theme.
- Replace `TURNSTILE_SITE_KEY` with the real site key.
- Keep the Turnstile script tag at the bottom of the template.
- Keep the hidden `website` input (honeypot).

## Ghost Admin
1) Create a page with slug `/contact/`.
2) Select the **Contact** template.
3) Publish.

## Why the website field exists
- It is a honeypot used to reject bots.
- Keep it hidden and `aria-hidden`.
