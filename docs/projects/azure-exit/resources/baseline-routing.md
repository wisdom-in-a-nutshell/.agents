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
| `adithyan.io` | Cloudflare proxied to `blog-personal-adi.azurewebsites.net`; App Service custom hostname bound directly | Remove stale Front Door custom domain references if present |
| `www.adithyan.io` | Cloudflare proxied to `blog-personal-adi.azurewebsites.net`; App Service custom hostname bound directly | Remove stale Front Door custom domain references if present |
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
