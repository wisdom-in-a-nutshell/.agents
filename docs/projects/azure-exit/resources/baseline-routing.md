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
