# Key Paths (repo-root relative)

## modal_functions
- AGENTS: `AGENTS.md`
- Repo-local Modal skill: `.agents/skills/modal-function-intake/SKILL.md`
- Registry: `src/registry.py`
- Functions: `src/functions/`
- Shared helpers: `src/common/`
- Client generator: `tools/generate_modal_client.py`
- Local WIN client sync: `scripts/local/sync_win_modal_client.sh`
- Registry validator: `tools/validate_registry.py`
- Deploy workflow: `.github/workflows/deploy-on-main.yml`
- Deploy entrypoint: `src/deploy.py`
- Secret manifest: `scripts/local/secrets/modal_secrets_manifest.json`
- Canonical local secret client: `~/GitHub/scripts/bin/local-secrets`
- Secret sync helper: `scripts/local/secrets/sync_local_to_modal_secrets.py`
- Secret env rules: `docs/rules/environment-variables.md`
- Secret flow doc: `docs/architecture/modal-secret-sync-flow.md`

## win
- AGENTS: `AGENTS.md`
- Generated client: `services/modal/client_generated.py` (do not edit)
- Wrapper client: `services/modal/client.py`
- Tests: `tests/services/modal/test_client.py`
- Modal integration guidance: `docs/references/modal-service-integration-guidance.md`
