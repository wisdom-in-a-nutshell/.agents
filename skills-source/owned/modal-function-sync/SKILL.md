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

### 4) Client sync (automatic)
- The deploy workflow in `.github/workflows/deploy-on-main.yml` generates and pushes `services/modal/client_generated.py` into `win` on push to `main`.
- Do not hand-edit `services/modal/client_generated.py`.
- Only generate locally when CI is unavailable or you need to validate before pushing.

### 5) Win integration
- Use `ModalClientGenerated` from `services/modal/client_generated.py`.
- Add wrapper/helper methods in `services/modal/client.py` if needed for ergonomics.
- Update tests in `tests/services/modal/test_client.py` and any call sites.

### 6) Deploy + verify
- Push to `main`, watch CI: lint/tests/deploy plus client sync.
- Rebase `win` after CI pushes the client update.
- Verify critical flows or run targeted tests.

## Common pitfalls
- Docs-only changes won't trigger deploy or sync (workflow ignores `docs/**` and `*.md`).
- Missing registry entries means the client will not include the function.
- Missing `MODAL_WIN_SYNC_PAT` breaks sync; CI will fail.

## References
- See `references/paths.md` for key files and repo entry points.
