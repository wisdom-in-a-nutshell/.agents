---
name: modal-function-sync
description: Implement or update Modal functions in modal_functions and ensure they are exposed/synced into win via the generated client. Use when a user says "Implement this in modal," wants a new Modal function/pipeline, or needs the two repos wired together.
---

# Modal Function Sync

## Overview
Use this skill to add or modify Modal functions in `modal_functions`, register them, and locally sync the generated client into `win`.

## Auto-generation rules
- `modal_functions` is the source of truth; never implement Modal entrypoints directly in `win`.
- `services/modal/client_generated.py` is generated from the `modal_functions` registry; do not edit it by hand.
- Sync is local-first from the sibling checkout with `scripts/local/sync_win_modal_client.sh`.
- Check drift without mutating `win` with `scripts/local/check_win_modal_client_drift.sh`.
- CI validates and deploys Modal functions; it does not commit generated client files into `win`.
- Generate locally to `tmp/client_generated.py` for fast validation without dirtying `win`.
- Generate into `../win/services/modal/client_generated.py` through the local sync wrapper before testing `win` wrappers/call sites.
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
- Update `src/deploy.py` so Modal actually ships the symbol.
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

### 5) Client sync (local generated output)
- Run the local sync wrapper from `modal_functions`:
  ```bash
  scripts/local/sync_win_modal_client.sh
  ```
- The wrapper validates the registry, generates `../win/services/modal/client_generated.py`, and formats it with WIN's Ruff config.
- Do not hand-edit `services/modal/client_generated.py`.
- Use `python tools/generate_modal_client.py --output tmp/client_generated.py` for local validation without touching `win`.
- Use `scripts/local/check_win_modal_client_drift.sh` when you need a check-only stale-client guardrail.
- Include generated client changes in the `win` worktree when the registry output changed.

### 6) Win integration
- Use `ModalClientGenerated` from `services/modal/client_generated.py`.
- Add wrapper/helper methods in `services/modal/client.py` if needed for ergonomics.
- Update tests in `tests/services/modal/test_client.py` and any call sites.

### 7) Deploy + verify
- Push to `main`, watch CI: lint/tests/deploy.
- In the deploy job, confirm the secret-refresh step passes when the change touches managed Modal secrets.
- Verify critical flows or run targeted tests in `win`.

## Common pitfalls
- Docs-only changes won't trigger Modal deploy (workflow ignores `docs/**` and `*.md`).
- Missing registry entries means the client will not include the function.
- Adding `modal.Secret.from_name(...)` in code without updating the manifest reintroduces secret drift.
- Adding a manifest entry without a real Key Vault backing secret will make deploy-time secret sync fail.
- Direct edits to generated client output will be overwritten by the local sync wrapper.

## References
- See `references/paths.md` for key files and repo entry points.
- See `references/modal-secrets.md` for the secret-management checklist.
