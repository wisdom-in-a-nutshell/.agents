# Key Paths (repo-root relative)

## modal_functions
- AGENTS: `AGENTS.md`, `src/AGENTS.md`, `src/functions/AGENTS.md`, `docs/AGENTS.md`, `docs/projects/AGENTS.md`
- Registry: `src/registry.py`
- Functions: `src/functions/`
- Shared helpers: `src/common/`
- Client generator: `tools/generate_modal_client.py`
- Registry validator: `tools/validate_registry.py`
- Deploy workflow: `.github/workflows/deploy-on-main.yml`
- Deploy entrypoint: `src/deploy.py`
- Secret manifest: `scripts/local/secrets/modal_secrets_manifest.json`
- Secret backfill helper: `scripts/local/secrets/backfill_modal_secret_to_keyvault.py`
- Secret sync helper: `scripts/local/secrets/sync_keyvault_to_modal_secrets.py`
- Secret env rules: `docs/rules/environment-variables.md`
- Secret flow doc: `docs/architecture/modal-secret-sync-flow.md`

## win
- AGENTS: `AGENTS.md`, `services/modal/AGENTS.md`, `docs/AGENTS.md`
- Generated client: `services/modal/client_generated.py` (do not edit)
- Wrapper client: `services/modal/client.py`
- Tests: `tests/services/modal/test_client.py`
