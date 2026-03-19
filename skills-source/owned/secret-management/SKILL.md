---
name: secret-management
description: "Manage secrets correctly in this environment: decide whether a value belongs in Azure Key Vault runtime config, repo-local `.env` bootstrap, machine-local `~/.secrets`, or GitHub Actions; choose naming; and update the right files, workflows, and docs when adding or moving a secret."
---

# Secret Management

## Overview

Use this skill to answer three questions:

1. Which lane owns this secret?
2. Which files, names, and validation steps must change?
3. How should the secret be documented so future agents do it the same way?

Read [references/decision-guide.md](references/decision-guide.md) for the concrete matrix, examples, naming rules, and file targets.

## Workflow

1. Identify the secret's primary consumer.
   - Running app in Azure
   - Local development in one repo
   - Shared operator tooling across repos on one machine
   - GitHub Actions only

2. Pick one primary lane.
   - Avoid giving the same secret family multiple hand-maintained homes.
   - If the value must appear in another lane, generate it from the same Key Vault secret instead of inventing a second owner.

3. Apply the lane-specific changes.
   - Use the checklist in [references/decision-guide.md](references/decision-guide.md).

4. Update durable docs when the pattern is new.
   - Prefer repo docs/reference updates over ad-hoc chat-only explanations.

## Lanes

### Runtime

Use for deployed application secrets.

- Store the value in Azure Key Vault.
- Prefer App Service Key Vault references instead of literal app settings.
- If local repo development also needs the value, map it into that repo's generated `.env` from the same Key Vault secret.

### Repo-Local

Use for secrets needed in one repo's local development workflow.

- Keep the value canonical in Key Vault.
- Map it into the repo's local bootstrap (`keyvault_env_map.env` or equivalent).
- Keep `.env.example` as placeholder-only documentation.

### Machine-Local Shared

Use for credentials shared across repos on one machine for operator tooling.

- Keep the value canonical in Key Vault.
- Sync it to `~/.secrets/<integration>/...`.
- Source it from shell bootstrap only as a generated machine-local file.
- Do not store secret values in `~/.agents` or tracked shell config.

### GitHub CI

Use only for CI bootstrap/auth or intentionally CI-only third-party credentials.

- Azure identifiers belong in GitHub `vars`, not `secrets`.
- Prefer Azure OIDC over long-lived Azure credential blobs.
- If CI needs a real runtime secret, fetch it after Azure login instead of making GitHub the owner.

## Naming Rules

- Repo-owned Key Vault families: `repo--secret-name`
- Shared integration families: `integration--secret-name`
- Machine-local integrations: match the folder name under `~/.secrets/<integration>/`
- GitHub secret names should be explicit about purpose, not repo history

## Guardrails

- Do not add a new secret to GitHub Actions just because it is convenient.
- Do not put literal secret values in `.zshrc`, tracked YAML, or committed config files.
- Do not create a machine-local integration when repo-local bootstrap is the real fit.
- Treat file-based credentials as a separate case; they may need materialization, not `KEY=value` sync.
