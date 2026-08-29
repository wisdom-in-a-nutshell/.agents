---
name: show-password-setup
description: Deprecated migration-only support for rotating an existing AIPodcasting show password while APP_ACCESS_MODE=password. Do not use for new shows; the target is one whole-app Cloudflare Access login, after which this skill is retired.
---

# Show Password Setup

> Deprecated. Do not provision a password for a new show. This skill remains available only for an
> emergency rotation while production still uses `APP_ACCESS_MODE=password`. The approved target is
> one Cloudflare Access login for the complete app, documented in
> `/Users/dobby/GitHub/aipodcasting/docs/references/access-and-client-api.md`.

## Overview

Rotate an existing show-specific password for the AIPodcasting frontend by setting the correct
`PASSWORD_SHOW_<SHOWNAME>` env var through the repo's local secret-store-backed runtime contract.
Refuse new-show setup and explain that approved human users will authenticate once at Cloudflare
Access and can then see every show.

## Workflow

1. **Collect inputs**
   - Show name (should match the `?show=` value used in URLs; typically the WIN `podcast_name`).
   - Password string.
   - Local secret scope (defaults to `shared`).
   - Confirm this is an emergency rotation for an already configured mapping and that the runtime
     still has `APP_ACCESS_MODE=password`. Otherwise stop and route to the Cloudflare cutover doc.

2. **Normalize the show ID**
   - Uppercase.
   - Non-alphanumeric => `_`.
   - Collapse multiple `_`.
   - Trim leading/trailing `_`.

3. **Set the canonical local secret**
   - Secret name pattern: `aipodcasting-app--password-show-<show-slug>`.
   - Write the password with `~/GitHub/scripts/bin/local-secrets`; never print the value.

4. **Update the runtime mapping + bootstrap `.env`**
   - Replace the existing mapping in `scripts/local/secrets/secret_env_map.env`.
   - Mirror it in `scripts/local/secrets/secret_env_map.env.example` for repo contract consistency.
   - Do not add a mapping for a new show.
   - Regenerate local `.env` via `scripts/local/secrets/bootstrap_local_env.sh`.
   - Keep secret values out of git.

5. **Reload local production**
   - Restart launchd service `com.<user>.aipodcasting-app` so it reads the regenerated `.env`.
   - Require `http://127.0.0.1:8800/api/health` to recover before reporting success.
   - The script skips this step only when the production service is not installed or
     `RELOAD_SERVICE=0` is set explicitly.

6. **Confirm**
   - Echo the env var name, canonical secret name, mapping path, and local service result.

## Script

Run the helper script:

```bash
bash "$HOME/GitHub/aipodcasting/.agents/skills/show-password-setup/scripts/set_show_password.sh"
```

The script will:
- Prompt for show name + password.
- Normalize the show name to the env var suffix.
- Write the password to the canonical local store.
- Upsert repo mapping files and refresh local `.env` from that store.
- Restart and health-check the Mac production frontend when it is installed.

The helper verifies that the tracked runtime mode is still `password` and refuses to create a new
show mapping. The agent should still explain the deprecated status before running it.

## References

- `scripts/set_show_password.sh`: canonical provisioning and local service reload helper.
- `/Users/dobby/GitHub/aipodcasting/docs/references/mac-mini-runtime.md`: frontend runtime,
  environment, health, and recovery contract.
