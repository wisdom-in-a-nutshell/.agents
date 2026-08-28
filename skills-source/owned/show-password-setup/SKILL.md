---
name: show-password-setup
description: Set up or rotate a show-specific password gate for AIPodcasting studio routes. Use when adding a new show or changing access for `/content/episodes/*?show=SHOW_NAME`, so `PASSWORD_SHOW_SHOWNAME` is stored in Key Vault, materialized into the generated local runtime env, and loaded by the Mac production service.
---

# Show Password Setup

## Overview

Provision a show-specific password for the AIPodcasting frontend by setting the correct
`PASSWORD_SHOW_<SHOWNAME>` env var through the repo's Key Vault-backed local runtime contract. This
mirrors the middleware-based password protection flow used by the studios.

## Workflow

1. **Collect inputs**
   - Show name (should match the `?show=` value used in URLs; typically the WIN `podcast_name`).
   - Password string.
   - Key Vault name (defaults to `kv-shared-repos`).

2. **Normalize the show ID**
   - Uppercase.
   - Non-alphanumeric => `_`.
   - Collapse multiple `_`.
   - Trim leading/trailing `_`.

3. **Set Key Vault secret**
   - Secret name pattern: `aipodcasting-app--password-show-<show-slug>`.
   - Write password value to Key Vault (`kv-shared-repos` by default).

4. **Update the runtime mapping + bootstrap `.env`**
   - Add/replace mapping in `scripts/local/secrets/keyvault_env_map.env`.
   - Mirror mapping in `scripts/local/secrets/keyvault_env_map.env.example` for repo contract consistency.
   - Regenerate local `.env` via `scripts/local/secrets/bootstrap_local_env_from_keyvault.sh`.
   - Keep secret values out of git.

5. **Reload local production**
   - Restart launchd service `com.<user>.aipodcasting-app` so it reads the regenerated `.env`.
   - Require `http://127.0.0.1:8800/api/health` to recover before reporting success.
   - The script skips this step only when the production service is not installed or
     `RELOAD_SERVICE=0` is set explicitly.

6. **Confirm**
   - Echo the env var name, Key Vault secret name, mapping path, and local service result.

## Script

Run the helper script:

```bash
bash "$HOME/GitHub/aipodcasting/.agents/skills/show-password-setup/scripts/set_show_password.sh"
```

The script will:
- Prompt for show name + password.
- Normalize the show name to the env var suffix.
- Write the password to Key Vault.
- Upsert repo mapping files and refresh local `.env` from Key Vault.
- Restart and health-check the Mac production frontend when it is installed.

## References

- `scripts/set_show_password.sh`: canonical provisioning and local service reload helper.
- `/Users/dobby/GitHub/aipodcasting/docs/references/mac-mini-runtime.md`: frontend runtime,
  environment, health, and recovery contract.
