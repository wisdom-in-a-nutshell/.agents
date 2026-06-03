# Baseline Routing

Date: 2026-05-29

## Initial Audit Facts
- Azure subscription: `Microsoft Azure Sponsorship` / `b75af65c-9650-4195-9cd8-eb173d733bf9`.
- Front Door profile: `ghost-front-door` in resource group `ghost`.
- App Service plan: `ASP-aipodcastinggroup-aef6` in resource group `aipodcasting`.
- Cloudflare zones visible through local token: `adithyan.io`, `aipodcast.ing`, `videoprocess.ing`, `wisdominanutshell.academy`.
- Cloudflare token can audit DNS records, but returned `403` for account-level tunnel, Pages, Workers, R2, rulesets, and zone settings endpoints.

## Public Routing Snapshot
| Hostname | Observed Route | Cleanup Decision |
| --- | --- | --- |
| `adithyan.io` | Cloudflare proxied to Mac mini tunnel `f1037d14-4b4b-4f72-8f6f-cac8bfe38119.cfargotunnel.com`; tunnel ingress to `127.0.0.1:8793` | Monitor, then remove remaining Azure Web App resources when comfortable. Azure deploy workflow removed. |
| `www.adithyan.io` | Cloudflare proxied to Mac mini tunnel `f1037d14-4b4b-4f72-8f6f-cac8bfe38119.cfargotunnel.com`; tunnel ingress to `127.0.0.1:8793` | Monitor, then remove remaining Azure Web App resources when comfortable. Azure deploy workflow removed. |
| `mindreader.adithyan.io` | Cloudflare proxied to `whos-in-your-head-adi.azurewebsites.net` | Keep |
| `aipodcast.ing` | DNS-only to `ghost-endpoint-cpg9bkeyfrdedfbq.z02.azurefd.net` | Keep until planned migration |
| `app.aipodcast.ing` | DNS-only to `ghost-endpoint-cpg9bkeyfrdedfbq.z02.azurefd.net` | Keep until planned migration |
| `thoughtforms-life.aipodcast.ing` | DNS-only to `ghost-endpoint-cpg9bkeyfrdedfbq.z02.azurefd.net` | Keep until planned migration |
| `podcast.futureoflife.org` | DNS to Azure Front Door endpoint | Keep until owner/zone access confirmed |
| `llm.aipodcast.ing` | DNS-only to `aip-litellm-proxy.azurewebsites.net` | Keep |
| `blog.aipodcast.ing` | DNS-only to `ghost-endpoint-cpg9bkeyfrdedfbq.z02.azurefd.net`; `curl` returned 404 | Remove after verifying no active Front Door custom domain route |
| `cursorcast.aipodcast.ing` | DNS-only to `cursorcast-aipodcast-ing-dcghe8d9f0e4caf9.z02.azurefd.net`; `curl` returned 404 | Remove DNS record if no active Azure owner exists |

## Change Log
- 2026-05-29: Created baseline resource note before approved cleanup.
- 2026-05-29: Deleted Cloudflare DNS records:
  - `blog.aipodcast.ing` CNAME -> `ghost-endpoint-cpg9bkeyfrdedfbq.z02.azurefd.net`
  - `cursorcast.aipodcast.ing` CNAME -> `cursorcast-aipodcast-ing-dcghe8d9f0e4caf9.z02.azurefd.net`
  - `_dnsauth.blog.aipodcast.ing` TXT
  - `_dnsauth.cursorcast.aipodcast.ing` TXT
- 2026-05-29: Deleted Azure Front Door routes:
  - `blog-personal-route`
  - `blog-personal-static-route`
- 2026-05-29: Requested deletion of Azure Front Door custom domains:
  - `adithyan-io` / `adithyan.io` — Azure state: `Deleting`
  - `www-adithyan-io` / `www.adithyan.io` — Azure state: `Deleting`
- 2026-05-29: Validation results:
  - `dig @gerald.ns.cloudflare.com blog.aipodcast.ing` returned no records.
  - `dig @gerald.ns.cloudflare.com cursorcast.aipodcast.ing` returned no records.
  - `curl -ksSI https://blog.aipodcast.ing` failed to resolve, expected after DNS deletion.
  - `curl -ksSI https://cursorcast.aipodcast.ing` failed to resolve, expected after DNS deletion.
  - `https://adithyan.io` returned HTTP 200 with `server: cloudflare`.
  - `https://www.adithyan.io` returned HTTP 200 with `server: cloudflare`.
  - `https://aipodcast.ing` returned HTTP 200 with `x-azure-ref`.
  - `https://app.aipodcast.ing` returned HTTP 307 with `x-azure-ref`.
  - `https://thoughtforms-life.aipodcast.ing` returned HTTP 200 with `x-azure-ref`.
- 2026-05-29: Follow-up audit confirmed `adithyan-io` and `www-adithyan-io` disappeared from Front Door custom-domain list.
- 2026-06-03: Cut over Cloudflare DNS records for `adithyan.io` and `www.adithyan.io` from `blog-personal-adi.azurewebsites.net` to `f1037d14-4b4b-4f72-8f6f-cac8bfe38119.cfargotunnel.com`, proxied.
- 2026-06-03: Added shared tunnel ingress:
  - `adithyan.io` -> `http://127.0.0.1:8793`
  - `www.adithyan.io` -> `http://127.0.0.1:8793`
- 2026-06-03: Validation results:
  - `https://adithyan.io/api/health` returned HTTP 200 with `{"service":"blog-personal","status":"ok"}`.
  - `https://www.adithyan.io/api/health` returned HTTP 200 with `{"service":"blog-personal","status":"ok"}`.
  - `https://adithyan.io/`, `https://www.adithyan.io/`, and `https://adithyan.io/blog` returned HTTP 200.
- 2026-06-03: Removed the `blog-personal` GitHub Actions Azure Web App deploy workflow after Mac mini cutover validation.
- 2026-05-29: Remaining Front Door routes/custom domains after cleanup:
  - `thoughtforms-route` -> `thoughtforms-life.aipodcast.ing` -> `thoughtforms-life.azurewebsites.net`
  - `aipodcasting-landing-route` -> `aipodcast.ing` -> `aipodcasting-public-website.azurewebsites.net`
  - `aipodcasting-app-route` -> `app.aipodcast.ing` -> `aipodcasting-app.azurewebsites.net`
  - `podcast-futureoflife-route` -> `podcast.futureoflife.org` -> `future-of-life-institute-podcast-aipodcast-ing.azurewebsites.net`
  - `default-route` -> Front Door default endpoint -> `thoughtforms-life.azurewebsites.net`
- 2026-05-29: Migration caveat found: direct requests to the Front Door origins with the public hostname returned 404, while the default Azure origin hostnames respond differently. Do not flip DNS directly to the current App Service origins without a host binding/TLS plan.

## Deep Audit Summary
- App Service plan `ASP-aipodcastinggroup-aef6` is `P1mv3`, capacity 1, hosting 10 always-on Linux container apps.
- 14-day App Service plan averages: about 15.8% CPU and 38.4% memory.
- 14-day Front Door metrics: about 227k requests and 96 GB response size.
- Highest 14-day app request counts:
  - `future-of-life-institute-podcast-aipodcast-ing`: about 437k requests, about 1.7k 5xx.
  - `blog-personal-adi`: about 410k requests, 0 5xx.
  - `thoughtforms-life`: about 393k requests, about 1.6k 5xx.
  - `aipodcasting-app`: about 373k requests, about 18 5xx.
  - `aipodcasting-public-website`: about 243k requests, about 12.8k 5xx.
- Redis `aip-redis` is a likely later cleanup candidate: about 2.4 average connected clients, 0% memory, and 0.19 ops/sec over 14 days.
- PostgreSQL and MySQL are active and should not be treated as quick cleanup candidates.
- `ghost-backup-vault-lrs` listed no protected backup items during audit; `ghost-backup-vault` protects two Azure File Share items from `ghoststorage01`.
- ACR `aipodcasting` is Standard with about 21 GB stored.

## Recommended Next No-Change Step
Draft a migration runbook for `thoughtforms-life.aipodcast.ing` before applying any changes. The runbook should specify:
- Current Front Door route, origin group, and origin host header.
- Required App Service hostname binding and TLS/certificate path.
- Cloudflare DNS record target and whether it should be proxied.
- Expected response headers/status after migration.
- Smoke checks for homepage, redirects, Ghost admin/API if applicable, and asset loading.
- Rollback DNS target and validation commands.
