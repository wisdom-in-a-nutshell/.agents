---
name: show-password-setup
description: Retired AIPodcasting show-password workflow. Human access is now one whole-app Cloudflare Access exact-email allowlist; do not provision or rotate application passwords.
---

# Show Password Setup (Retired)

This workflow was retired on 2026-08-29. It is dormant in the agents registry and is not installed
in AIPodcasting or WIN.

Human browser access is one Cloudflare Access login for the complete application. The exact-email
allowlist, policy identifiers, and operating rules live in
`/Users/dobby/GitHub/aipodcasting/docs/references/access-and-client-api.md`.

Do not add `PASSWORD_*`, password-session cookies, `APP_ACCESS_MODE`, or frontend external bearer
keys. Customer agents use the separate scoped WIN `/client/v1/**` API through the `ai-podcasting`
skill; they do not use Cloudflare browser sessions.

If asked to change human access, edit the Cloudflare Access exact-email policy. If asked to enable a
customer agent, follow WIN's client-principal provisioning contract and the `ai-podcasting` client
setup reference.
