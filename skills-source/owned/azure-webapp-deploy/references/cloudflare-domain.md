# Cloudflare Custom Domain Flow

Use this when the user wants a Cloudflare-managed hostname for an Azure Web App.

## Required Inputs

- Domain or subdomain.
- Cloudflare zone name or ID.
- Azure Web App name and resource group.
- Azure Web App `customDomainVerificationId`.
- Certificate strategy:
  - existing wildcard Cloudflare Origin Certificate in Azure, or
  - Azure App Service managed certificate.

## Staged Flow

1. Create DNS records with the CNAME not proxied yet:
   - `<host>` CNAME -> `<app>.azurewebsites.net`, DNS-only
   - `asuid.<host>` TXT -> Azure `customDomainVerificationId`
2. Wait for public DNS to resolve both records.
3. Add Azure hostname binding:
   ```bash
   az webapp config hostname add \
     --resource-group <rg> \
     --webapp-name <app> \
     --hostname <host>
   ```
4. Bind TLS:
   - Existing origin cert:
     ```bash
     az webapp config ssl bind \
       --resource-group <rg> \
       --name <app> \
       --certificate-thumbprint <thumbprint> \
       --ssl-type SNI
     ```
   - Managed cert:
     ```bash
     az webapp config ssl create \
       --resource-group <rg> \
       --name <app> \
       --hostname <host>
     ```
5. Switch the Cloudflare CNAME to proxied if desired.
6. Verify through Cloudflare:
   ```bash
   curl -fsS https://<host>/api/health
   ```

## Lessons From A Proxied Azure Hostname

- DNS-only first made Azure hostname verification straightforward.
- An existing wildcard Cloudflare Origin Certificate in Azure can be better than
  waiting on a new App Service managed certificate for a proxied Cloudflare hostname.
- Local DNS caches can keep resolving the direct Azure CNAME briefly after
  proxying. Verify public DNS and, when needed, force a Cloudflare IP during
  diagnosis with curl `--resolve`.
