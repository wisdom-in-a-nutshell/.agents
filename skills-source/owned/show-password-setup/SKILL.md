---
name: show-password-setup
description: Set up or rotate a show-specific password gate for AIPodcasting studio routes. Use when adding a new show or changing access for `/content/episodes/*?show=SHOW_NAME`, so `PASSWORD_SHOW_SHOWNAME` is stored in Key Vault and app settings use Key Vault references.
---

# Show Password Setup

## Overview

Provision a show-specific password for the AIPodcasting frontend by setting the correct
`PASSWORD_SHOW_<SHOWNAME>` env var through Key Vault-backed app settings. This mirrors the middleware-based
password protection flow used by the studios.

## Workflow

1. **Collect inputs**
   - Show name (should match the `?show=` value used in URLs; typically the WIN `podcast_name`).
   - Password string.
   - Azure resource group (optional; auto-detected if possible).
   - Key Vault name (defaults to `kv-shared-repos`).

2. **Normalize the show ID**
   - Uppercase.
   - Non-alphanumeric => `_`.
   - Collapse multiple `_`.
   - Trim leading/trailing `_`.

3. **Set Key Vault secret**
   - Secret name pattern: `aipodcasting-app--password-show-<show-slug>`.
   - Write password value to Key Vault (`kv-shared-repos` by default).

4. **Set Azure env var to Key Vault reference**
   - App: `aipodcasting-app`.
   - Var: `PASSWORD_SHOW_<SHOWNAME>`.
   - Value format:
     `@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/<secret-name>/)`
   - Use Azure CLI (`az webapp config appsettings set`).

5. **Update local mapping + bootstrap `.env`**
   - Add/replace mapping in `scripts/local/secrets/keyvault_env_map.env`.
   - Mirror mapping in `scripts/local/secrets/keyvault_env_map.env.example` for repo contract consistency.
   - Regenerate local `.env` via `scripts/local/secrets/bootstrap_local_env_from_keyvault.sh`.
   - Keep secret values out of git.

6. **Confirm**
   - Echo env var name, Key Vault secret name, and target app.

## Script

Run the helper script:

```bash
bash "$HOME/GitHub/aipodcasting/.agents/skills/show-password-setup/scripts/set_show_password.sh"
```

The script will:
- Prompt for show name + password.
- Normalize the show name to the env var suffix.
- Write the password to Key Vault.
- Set the Azure App Service env var for `aipodcasting-app` as a Key Vault reference.
- Upsert repo mapping files and refresh local `.env` from Key Vault.

## Resources (optional)

Create only the resource directories this skill actually needs. Delete this section if no resources are required.

### scripts/
Executable code (Python/Bash/etc.) that can be run directly to perform specific operations.
