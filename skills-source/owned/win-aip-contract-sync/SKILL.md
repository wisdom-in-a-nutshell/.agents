---
name: win-aip-contract-sync
description: Local-first WIN-to-AIP contract workflow. Use when adding or changing WIN job endpoints, public response DTOs, generated frontend contracts, or AIP frontend code that consumes WIN contracts in aipodcasting.
---

# WIN AIP Contract Sync

## Use when
- A WIN backend job endpoint or public DTO must be available in `../aipodcasting`.
- AIP frontend code needs generated job paths, job types, or DTO types from WIN.
- Contract sync, generated AIP types, or `lib/aip/contracts/**` drift is involved.

## Operating Rules
- `win` owns contract sources; `aipodcasting/lib/aip/contracts/**` is generated output.
- Run local sync; do not wait for CI or cloud cross-repo sync.
- Do not hand-edit generated files under `aipodcasting/lib/aip/contracts/**`.
- Keep database models internal; expose public DTOs only.
- Ask only when frontend fields or UX placement cannot be inferred safely.
- Do not commit or push unless the user explicitly asks or repo-local automation handles it.

## Workflow
1. Inspect repo state:
   ```bash
   git -C /Users/dobby/GitHub/win status -sb
   git -C /Users/dobby/GitHub/aipodcasting status -sb
   ```
   Work around unrelated local changes; do not revert them.
2. For backend changes in `win`:
   - For job endpoints, keep `@register_endpoint` metadata and request/result schemas contractable.
   - For synchronous UI data, define or update a public Pydantic response DTO and set `response_model=...`.
   - Add frontend-consumed DTOs to `PUBLIC_DTOS` in `scripts/contracts/export_public_dto_contracts.py`.
   - Map DB/internal models to DTOs explicitly.
3. Run generated sync from `win`:
   ```bash
   cd /Users/dobby/GitHub/win
   scripts/local/sync_aip_contracts.sh
   ```
   The wrapper exports job contracts, clears stale generated DTO output, writes current DTOs, and formats with AIP's Biome config.
4. If frontend work is needed in `aipodcasting`:
   - Import generated types from `lib/aip/contracts/**`.
   - Submit jobs through the generic AIP job proxy using generated endpoint IDs/paths.
   - For synchronous reads or writes, add thin Next.js API proxies to WIN; do not add MongoDB access.
   - Keep feature-local filters, form state, and UI-only types outside generated contracts.
5. Validate:
   - Confirm expected generated files exist under `../aipodcasting/lib/aip/contracts/**`.
   - Run focused backend tests for changed WIN contract exporters or handlers.
   - Run `pnpm type-check` in `../aipodcasting` when frontend TypeScript or contract consumers changed.
   - Report `git status -sb` for both repos.

## References
- `win/AGENTS.md`
- `win/docs/references/api-endpoint-implementation.md`
- `win/docs/references/scripts-and-tools-reference.md`
- `win/scripts/local/sync_aip_contracts.sh`
- `aipodcasting/AGENTS.md`
- `aipodcasting/docs/references/aip-backend-integration.md`
- `aipodcasting/docs/references/aip-integration-patterns.md`
