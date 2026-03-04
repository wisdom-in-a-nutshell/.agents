---
name: azure-webapp-config
description: Manage Azure App Service app settings across repos with reusable profiles. Use when adding/updating/removing environment variables in Azure Web Apps (single app or multi-app) and keeping local env files aligned.
---

# Azure WebApp Config

## Overview

Use this shared skill for Azure Web App appsettings operations.

- Supports one or multiple apps per run.
- Supports repo-specific profiles from `references/profiles.tsv`.
- Supports direct targeting via `--app` + `--resource-group` without profiles.

## Workflow

1. Pick a target method:
   - `--profile <name>` for known repo/app groups.
   - `--app <name> --resource-group <rg>` for ad-hoc targets.
2. Stage settings with one or both:
   - `--set KEY=VALUE` (repeatable)
   - `--env-file <path>`
3. Run with `--dry-run` first.
4. Re-run without `--dry-run` to apply.
5. Optionally add `--restart` to force app restart after settings update.

For secret-like settings, use Key Vault reference values:
- `@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/<secret-name>/)`
- Do not write raw secret values directly into appsettings.

## Commands

List available profiles:

```bash
python3 .agents/skills/azure-webapp-config/scripts/set_appsettings.py --list-profiles
```

Apply settings via profile:

```bash
python3 .agents/skills/azure-webapp-config/scripts/set_appsettings.py \
  --profile win-backend \
  --set EXAMPLE_FLAG=true \
  --dry-run
```

Apply Key Vault reference via profile:

```bash
python3 .agents/skills/azure-webapp-config/scripts/set_appsettings.py \
  --profile win-backend \
  --set \"EXAMPLE_SECRET=@Microsoft.KeyVault(SecretUri=https://kv-shared-repos.vault.azure.net/secrets/win--example-secret/)\" \
  --dry-run
```

Apply settings via explicit app target:

```bash
python3 .agents/skills/azure-webapp-config/scripts/set_appsettings.py \
  --app aipodcasting-app \
  --resource-group aipodcasting \
  --set FEATURE_X=true
```

## Notes

- This skill only manages Azure appsettings.
- Repo-specific post-steps (for example rebuilding Modal secrets) should remain in repo-local wrapper skills.
- Keep secrets out of git-tracked files.
- `--env-file` is powerful; avoid feeding `.env` blindly to production apps.
