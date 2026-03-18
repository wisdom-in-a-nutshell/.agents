# Secret Decision Guide

Use this when adding or moving a secret in this environment.

## Decision Tree

### 1. Is the secret for a running deployed app?

Use the `runtime` lane.

- Store the value in Azure Key Vault.
- Wire the app to consume it via runtime config, ideally a Key Vault reference.
- If local development also needs it, map the same secret family into the repo-local `.env` bootstrap.

Typical examples:
- `aipodcasting--mongodb-uri`
- `litellm--master-key`
- app-specific `LLM_API_KEY`

### 2. Is the secret only for local work in one repo?

Use the `repo-local` lane.

- Add/update the repo's `scripts/local/secrets/keyvault_env_map.env` or equivalent.
- Keep the real value in Key Vault.
- Update `.env.example` only with a placeholder if the repo documents local envs there.

Typical examples:
- repo-specific database URIs
- repo-specific service API keys used in local scripts

### 3. Is the secret shared across repos on one machine for operator tooling?

Use the `machine-local shared` lane.

- Put the canonical value in Key Vault.
- Add a machine-secret mapping under `~/GitHub/scripts/sync/machine-secrets/*.env.map`.
- Generate `~/.secrets/<integration>/env`.
- Source that generated file from shell bootstrap.

Typical examples:
- `reddit--client-id` and related Reddit auth
- `cloudflare--api-token`
- `github--org-admin-token`

### 4. Is the secret only for GitHub Actions automation?

Use the `GitHub CI` lane.

- Keep only CI bootstrap/auth or deliberate CI-only third-party credentials in GitHub.
- Use `vars` for non-secret identifiers such as Azure client/tenant/subscription IDs.
- Prefer OIDC for Azure access.

Typical examples:
- `CROSS_REPO_SYNC_PAT`
- Ghost deploy keys

## File Targets In This Environment

### Runtime / Key Vault

Canonical docs:
- `/Users/dobby/GitHub/scripts/docs/architecture/secret-source-of-truth-flow.md`
- `/Users/dobby/GitHub/scripts/docs/references/azure-key-vault-structure.md`

### Repo-Local

Typical files inside an app repo:
- `scripts/local/secrets/keyvault_env_map.env`
- `scripts/local/secrets/bootstrap_local_env_from_keyvault.sh`
- `.env.example`

### Machine-Local Shared

Typical files:
- `/Users/dobby/GitHub/scripts/sync/machine-secrets/<integration>.env.map`
- `/Users/dobby/GitHub/scripts/sync/keyvault-sync-machine-secrets.sh`
- `/Users/dobby/GitHub/scripts/setup/codex/zshrc.shared`
- `~/.secrets/<integration>/env`

### GitHub CI

Typical files:
- `.github/workflows/*.yml`
- GitHub repo/org `vars`
- GitHub repo/org `secrets`

## Naming

### Key Vault

- Repo-owned family: `repo--name`
- Shared integration family: `integration--name`

Good:
- `aipodcasting--mongodb-uri`
- `github--org-admin-token`
- `cloudflare--api-token`

Avoid:
- generic names with unclear owner
- reusing one family for unrelated apps

### GitHub Actions

Prefer names that describe purpose directly.

Good:
- `CROSS_REPO_SYNC_PAT`
- `GHOST_ADMIN_API_KEY`

Avoid:
- names tied to old workflow history when the current purpose is narrower

## Exceptions

### File-based credentials

Do not force these into the simple `KEY=value` machine-secret pattern.

Example:
- App Store Connect `.p8` key material

Use a materialization pattern instead: store in Key Vault if appropriate, then write the file locally at execution/bootstrap time.

### Session-like local tokens

Do not rush these into Key Vault just because they are secrets.

Example:
- tokens scraped from a local app cache such as Superwhisper

Treat them as local/session credentials unless they become durable shared credentials.

## Validation Checklist

- Search the repo and workflows to confirm whether the secret family already exists.
- Confirm there is only one primary owner lane.
- Validate bootstrap/sync after changes.
- Update durable docs if you introduced a new repeatable pattern.
