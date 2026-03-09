# Modal Secrets Checklist

Use this when a Modal function change adds, removes, or changes
`modal.Secret.from_name(...)`.

## Default Rule

- Treat Azure Key Vault as the source of truth.
- Treat Modal secrets as deploy-time runtime copies.
- If the secret is a stable runtime dependency, add it to
  `scripts/local/secrets/modal_secrets_manifest.json`.

## Normal Path For A New Stable Secret

1. Pick the canonical Azure Key Vault secret name.
2. Ensure the Key Vault secret exists.
3. Add the Modal secret payload mapping to
   `scripts/local/secrets/modal_secrets_manifest.json`.
4. Update `docs/rules/environment-variables.md` if the env shape or naming rule
   changes.
5. Push to `main` and watch `Deploy on Main`.
6. Confirm the `Refresh Modal runtime secrets from Key Vault` step passes.

## When Backfill Is Needed

Use
`scripts/local/secrets/backfill_modal_secret_to_keyvault.py`
when all of these are true:

- the secret already exists in Modal
- it is not yet in Azure Key Vault
- you want Key Vault to become the new source of truth

That helper is for one-time adoption of an older Modal-only secret into the
managed flow.

## Allowed Exceptions

It is acceptable to leave a secret outside the manifest only if there is a clear
documented reason, such as:

- it is rotated by a separate automation system
- it is intentionally short-lived or ephemeral
- it is owned by another platform and should not be mirrored from Key Vault

If you keep it outside the manifest, document that explicitly in the relevant
repo docs or tracker.

## Failure Modes To Avoid

- Adding `modal.Secret.from_name(...)` in code without adding the manifest entry
  for a stable secret
- Adding the manifest entry before the Key Vault secret exists
- Manually editing Modal secrets and assuming deploy will preserve that state
  when the secret is already manifest-managed

## Quick Verification

- `python tools/validate_registry.py`
- `python scripts/local/secrets/sync_keyvault_to_modal_secrets.py`
- Push and watch GitHub Actions `Deploy on Main`

