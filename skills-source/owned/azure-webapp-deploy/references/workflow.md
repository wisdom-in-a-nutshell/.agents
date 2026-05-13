# Azure Web App Deployment Workflow

## 1. Repo Preparation

Inspect the repo and decide whether it already has:

- Package manager lockfile.
- Production build command.
- Health endpoint.
- Dockerfile suitable for App Service.
- GitHub Actions deploy workflow.

For Next.js container deploys, prefer:

```ts
// next.config.ts
const nextConfig = {
  output: "standalone"
};
```

The Dockerfile should build the app and run the standalone server or equivalent
production server.

## 2. GitHub Actions

Use GitHub OIDC:

- `permissions.id-token: write`
- `permissions.contents: read`
- `environment: Production` when using environment-scoped federated credentials
- repo or environment vars:
  - `AZURE_CLIENT_ID`
  - `AZURE_TENANT_ID`
  - `AZURE_SUBSCRIPTION_ID`

Avoid GitHub secrets for runtime app configuration.

## 3. Azure App

Typical setup:

```bash
az webapp create \
  --resource-group <resource-group> \
  --plan <app-service-plan-id-or-name> \
  --name <app-name> \
  --deployment-container-image-name <acr-login-server>/<image-name>:latest

az webapp identity assign -g <resource-group> -n <app-name>
az role assignment create --assignee <principal-id> --role AcrPull --scope <acr-id>
az webapp config set -g <resource-group> -n <app-name> \
  --always-on true \
  --generic-configurations '{"acrUseManagedIdentityCreds": true}'
```

If runtime secrets are needed, prefer Key Vault references:

```bash
az role assignment create \
  --assignee <principal-id> \
  --role "Key Vault Secrets User" \
  --scope <key-vault-id>

az webapp config appsettings set -g <resource-group> -n <app-name> --settings \
  "LLM_API_ENDPOINT=@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/<endpoint-secret>/)" \
  "LLM_API_KEY=@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/<key-secret>/)"
```

## 4. Federated Credential

The Azure app registration used by GitHub Actions needs a subject matching the
workflow.

For environment-based workflows:

```text
repo:<owner>/<repo>:environment:Production
```

For branch-only workflows:

```text
repo:<owner>/<repo>:ref:refs/heads/main
```

Check before creating duplicates:

```bash
az ad app federated-credential list --id <azure-client-id>
```

## 5. Deploy

Let GitHub Actions build and push the image. Watch the run:

```bash
gh run list --repo <owner/repo> --limit 5
gh run watch <run-id> --repo <owner/repo> --interval 10 --exit-status
```

Confirm ACR and Web App image:

```bash
az acr repository show-tags --name <acr-name> --repository <image-name> --orderby time_desc --top 5
az webapp show -g <resource-group> -n <app-name> --query siteConfig.linuxFxVersion
```

## 6. Verify

Check the default hostname before adding a custom domain:

```bash
curl -fsS https://<app-name>.azurewebsites.net/api/health
```

Then check app-specific runtime status endpoints when available.
