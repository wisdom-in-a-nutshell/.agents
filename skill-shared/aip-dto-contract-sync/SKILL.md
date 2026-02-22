---
name: aip-dto-contract-sync
description: Expose WIN backend data to the AIP frontend via public DTOs and the contract sync workflow (win -> aipodcasting). Use when adding/updating API response models that must appear in the frontend.
---

# AIP DTO Contract Sync

## Use when
- You add or change a backend response DTO that the frontend must consume.
- You need to expose new backend data to `../aipodcasting` without manual type drift.

## Workflow
0. Confirm the minimal frontend fields required. As a rule, avoid exposing
   large payloads because the backend persists full data and the frontend can
   fetch from the database later. Default to a lightweight response (e.g.,
   `success` + optional `error`) unless the user explicitly requests more.
   If unclear, ask what the UI needs before defining or exporting DTOs.
1. Backend: define/adjust a public response DTO (Pydantic) in the API handler or shared domain model.
2. Ensure the route declares `response_model=YourDto` so it is contractable.
3. Keep DB models internal; map DB -> DTO in the handler/service (no direct DB schema exposure).
4. Add the DTO to `PUBLIC_DTOS` in `scripts/contracts/export_public_dto_contracts.py` (domain/name/module/attribute).
   - If you move handler modules (e.g., into `api/handlers/stages`, `api/handlers/orchestration`, `api/handlers/operations`), update the module path here.
5. Wait for `Deploy on Main` to succeed; `Sync Contracts` will auto-generate types into `../aipodcasting/lib/aip/contracts/dto/**`.
   - Prefer CI sync; only run the local export for debugging, and don’t commit those manual outputs.
   - If no DTOs changed or none are in `PUBLIC_DTOS`, the workflow may report "skip" while still succeeding.
6. Frontend: import generated types from `lib/aip/contracts/dto/<domain>/<name>.ts` and remove hand-written DTO types.
7. Keep feature-specific UI filter/query types local (non-contract types stay in the feature).

## Validation
- `Deploy on Main` succeeds in `win`.
- `Sync Contracts` workflow succeeds in `win`.
- Generated DTO file exists/updates in `../aipodcasting/lib/aip/contracts/dto/<domain>/<name>.ts`.
- Frontend typecheck/build passes.

## References
- `win/scripts/contracts/AGENTS.md`
- `win/services/database/AGENTS.md`
- `win/api/AGENTS.md`
- `win/.github/workflows/sync-contracts.yml`
- `../aipodcasting/lib/aip/AGENTS.md`
