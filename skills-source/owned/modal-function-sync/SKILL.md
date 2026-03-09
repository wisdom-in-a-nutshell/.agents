---
name: modal-function-sync
description: Implement or update Modal functions in modal_functions and ensure they are exposed/synced into win via the generated client. Use when a user says "Implement this in modal," wants a new Modal function/pipeline, or needs the two repos wired together.
---

# Modal Function Sync

## Overview
Use this skill to add or modify Modal functions in `modal_functions`, register them, and rely on CI to sync the generated client into `win`.

## Auto-generation rules
- `modal_functions` is the source of truth; never implement Modal entrypoints directly in `win`.
- `services/modal/client_generated.py` is CI-generated; do not edit it by hand.
- Sync happens on push to `main` (non-doc changes) via `.github/workflows/deploy-on-main.yml`.
- Use `workflow_dispatch` only when you need to trigger deploy/sync without code changes.
- Stable Modal runtime secrets should default to the Key Vault -> manifest -> Modal sync flow, not one-off manual Modal secret updates.

## Workflow

### 1) Gather context
- Ask for the new function or pipeline intent, inputs/outputs, storage/caching expectations, and where win will call it.
- Confirm whether the change is new functionality or a behavior update.

### 2) Read local guidance
- Open `AGENTS.md` in both repos (see `references/paths.md`) and follow nested rules.

### 3) Implement in modal_functions (source of truth)
- Add or modify code under `src/functions/...`.
- Update `src/registry.py` to expose the function.
- Update shared helpers in `src/common/` if needed.
- Run `python tools/validate_registry.py` when changing the registry.
- Keep the Modal app name consistent with `src/common/containers.py`.

### 4) Handle secrets and config deliberately
- Use `references/modal-secrets.md` as the checklist for secret ownership and manifest updates.
- If the change adds or modifies `modal.Secret.from_name(...)`, decide whether the secret is:
  - a stable runtime secret that should be managed from Azure Key Vault, or
  - an intentional exception owned by a separate system.
- Default rule: if it is a stable runtime secret, add it to `scripts/local/secrets/modal_secrets_manifest.json`.
- Ensure the backing Key Vault secret exists before relying on the manifest entry.
- If you are adopting an older Modal-only secret into the managed flow, use `scripts/local/secrets/backfill_modal_secret_to_keyvault.py` first so Key Vault becomes the source of truth without printing secret values.
- Update `docs/rules/environment-variables.md` when the secret shape or expected env keys change.
- Do not leave a new code-level `modal.Secret.from_name(...)` reference unmanaged unless the exception is explicitly documented.

### 5) Client sync (automatic)
- The deploy workflow in `.github/workflows/deploy-on-main.yml` generates and pushes `services/modal/client_generated.py` into `win` on push to `main`.
- Do not hand-edit `services/modal/client_generated.py`.
- Only generate locally when CI is unavailable or you need to validate before pushing.

### 6) Win integration
- Use `ModalClientGenerated` from `services/modal/client_generated.py`.
- Add wrapper/helper methods in `services/modal/client.py` if needed for ergonomics.
- Update tests in `tests/services/modal/test_client.py` and any call sites.

### 7) Deploy + verify
- Push to `main`, watch CI: lint/tests/deploy plus client sync.
- In the deploy job, confirm the secret-refresh step passes when the change touches managed Modal secrets.
- Rebase `win` after CI pushes the client update.
- Verify critical flows or run targeted tests.

## Common pitfalls
- Docs-only changes won't trigger deploy or sync (workflow ignores `docs/**` and `*.md`).
- Missing registry entries means the client will not include the function.
- Missing `MODAL_WIN_SYNC_PAT` breaks sync; CI will fail.
- Adding `modal.Secret.from_name(...)` in code without updating the manifest reintroduces secret drift.
- Adding a manifest entry without a real Key Vault backing secret will make deploy-time secret sync fail.
- Manual local client generation is only for validation or CI-breakglass use; the normal path is CI-driven sync.

## References
- See `references/paths.md` for key files and repo entry points.
- See `references/modal-secrets.md` for the secret-management checklist.
