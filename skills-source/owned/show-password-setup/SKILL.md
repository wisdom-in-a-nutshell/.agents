---
name: show-password-setup
description: Set up or rotate a show-specific password gate for AIPodcasting studio routes. Use when adding a new show or changing access for `/content/episodes/*?show=SHOW_NAME`, so `PASSWORD_SHOW_SHOWNAME` is set in Azure (aipodcasting-app) and local `.env`.
---

# Show Password Setup

## Overview

Provision a show-specific password for the AIPodcasting frontend by setting the correct
`PASSWORD_SHOW_<SHOWNAME>` env var in Azure and local dev. This mirrors the middleware-based
password protection flow used by the studios.

## Workflow

1. **Collect inputs**
   - Show name (should match the `?show=` value used in URLs; typically the WIN `podcast_name`).
   - Password string.
   - Azure resource group (optional; auto-detected if possible).

2. **Normalize the show ID**
   - Uppercase.
   - Non-alphanumeric => `_`.
   - Collapse multiple `_`.
   - Trim leading/trailing `_`.

3. **Set Azure env var**
   - App: `aipodcasting-app`.
   - Var: `PASSWORD_SHOW_<SHOWNAME>`.
   - Use Azure CLI (`az webapp config appsettings set`).

4. **Update local `.env`**
   - Add/replace the same variable for local dev.
   - Keep secrets out of git.

5. **Confirm**
   - Echo the env var name and where it was set.

## Script

Run the helper script:

```bash
bash "$HOME/GitHub/aipodcasting/.agents/skills/show-password-setup/scripts/set_show_password.sh"
```

The script will:
- Prompt for show name + password.
- Normalize the show name to the env var suffix.
- Set the Azure App Service env var for `aipodcasting-app`.
- Add/update the same var in `.env`.

## Resources (optional)

Create only the resource directories this skill actually needs. Delete this section if no resources are required.

### scripts/
Executable code (Python/Bash/etc.) that can be run directly to perform specific operations.
