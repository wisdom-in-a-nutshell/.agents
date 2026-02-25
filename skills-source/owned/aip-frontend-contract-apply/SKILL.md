---
name: aip-frontend-contract-apply
description: Applies synced WIN → AIP contracts by implementing the frontend UI and feature wiring for new/updated backend job or DTO endpoints. Use when Deploy on Main and Sync Contracts must finish before rebasing ~/GitHub/aipodcasting, updating UI, and committing/pushing with CI verification.
---

# AIP Frontend Contract Apply

Use this workflow when backend DTO/job contracts have changed and the AIP frontend
must be updated **after** the Sync Contracts workflow finishes.

## Workflow

1. **Rebase + sync before edits**
   - Run `scripts/rebase_aipodcasting.sh` to commit any local changes, fetch, rebase, and push
     `~/GitHub/aipodcasting` on `origin/main` before any edits.

2. **Confirm UI requirements**
   - Ask where the frontend change should live (page, component path, feature area).
   - Ask what the structure should look like (layout, fields, buttons, UX flow).
   - If unclear, ask for a minimal UI spec before coding.

3. **Wait for contract sync (no local export)**
   - Do **not** run local contract export scripts.
   - Wait for `Deploy on Main` and `Sync Contracts` to complete successfully.
   - Only proceed once generated contracts exist in `~/GitHub/aipodcasting/lib/aip/contracts/`.
   - Confirm `lib/aip/contracts/job-endpoints.ts` contains the new endpoint ID.
   - Confirm the relevant DTO file exists under `lib/aip/contracts/dto/**` (if required).
   - If missing, stop and report that contract sync has not completed.

4. **Apply frontend changes**
   - Import generated contract types from `~/GitHub/aipodcasting/lib/aip/contracts/...`.
   - Do **not** hand-edit generated contract files.
   - Implement the UI and hook wiring following codebase patterns:
     - Read `~/GitHub/aipodcasting/lib/aip/AGENTS.md` for job/DTO patterns.
     - Read the closest feature `AGENTS.md` for UI placement and structure.
   - If there are unrelated changes in the codebase, note them and proceed (the rebase
     script commits all current changes).

5. **Commit, push, verify CI**
   - Commit frontend changes with a clear message.
   - Push and confirm CI passes for `~/GitHub/aipodcasting`.
   - Verify the working tree is clean after the push.
   - Run `git status -sb` and confirm no pending changes.

## Notes

- Keep contract-driven UI types minimal; only add fields the UI needs.
- If required contracts are missing, stop and report which sync output is absent.
