# Modal Secrets Checklist

Use this when a Modal function change adds, removes, or changes
`modal.Secret.from_name(...)`.

## Default Rule

- Treat `~/Documents/DobbySecrets` as the local canonical source of truth.
- Treat Modal secrets as deploy-time runtime copies.
- If the secret is a stable runtime dependency, add it to
  `scripts/local/secrets/modal_secrets_manifest.json`.

## Normal Path For A New Stable Secret

1. Pick the canonical local scope and secret name.
2. Ensure the value exists using `~/GitHub/scripts/bin/local-secrets`; never print it.
3. Add the Modal secret payload mapping to
   `scripts/local/secrets/modal_secrets_manifest.json`.
4. Update `docs/rules/environment-variables.md` if the env shape or naming rule
   changes.
5. Push to `main` and watch `Deploy on Main`.
6. Run the local Modal secret sync from the trusted Mac and confirm its structured summary passes.

## When Backfill Is Needed

Use `~/GitHub/scripts/bin/local-secrets set` when all of these are true:

- the secret already exists in Modal
- it is not yet in the local canonical store
- you want the local store to become the new source of truth

That helper is for one-time adoption of an older Modal-only secret into the
managed flow.

## Allowed Exceptions

It is acceptable to leave a secret outside the manifest only if there is a clear
documented reason, such as:

- it is rotated by a separate automation system
- it is intentionally short-lived or ephemeral
- it is owned by another platform and should not be mirrored from the local store

If you keep it outside the manifest, document that explicitly in the relevant
repo docs or tracker.

## Failure Modes To Avoid

- Adding `modal.Secret.from_name(...)` in code without adding the manifest entry
  for a stable secret
- Adding the manifest entry before the local canonical secret exists
- Manually editing Modal secrets and assuming deploy will preserve that state
  when the secret is already manifest-managed

## Quick Verification

- `python tools/validate_registry.py`
- `python scripts/local/secrets/sync_local_to_modal_secrets.py`
- Run the local deploy/sync path and verify the Modal destination
