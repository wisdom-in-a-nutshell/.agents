# Azure Exit

## Goal
Reduce avoidable Azure dependency and daily spend by migrating public edge, hosting, storage, cache, and observability responsibilities away from Azure in small validated steps.

## Why / Impact
The current deployment has a meaningful daily floor cost from Azure App Service Premium and Azure Front Door. The project should lower recurring spend and reduce platform lock-in without breaking public sites, Ghost content, app APIs, model routing, backups, or DNS ownership.

## Scope / Non-Goals
### In Scope
- Audit Azure resources, Cloudflare DNS/proxy state, and live public routes before changing anything.
- Remove stale or demonstrably unused Azure/Cloudflare routing resources after validation.
- Move public edge responsibilities from Azure Front Door to Cloudflare hostname by hostname.
- Identify and execute low-risk replacements for Redis, container registry storage, logging, and app hosting.
- Track decisions, validation evidence, and remaining migration risks here.

### Out of Scope
- Big-bang migration away from Azure.
- Database deletion or migration without a separate backup/restore plan.
- Breaking public DNS, mail DNS, custom TLS, Ghost content, or production app endpoints for cost savings.
- Manual git commit or push; repo automation handles normal sync.

## Context / Constraints
- Date started: 2026-05-29
- Azure subscription: `Microsoft Azure Sponsorship` / `b75af65c-9650-4195-9cd8-eb173d733bf9`.
- Cloudflare zones found through the local Cloudflare token: `adithyan.io`, `aipodcast.ing`, `videoprocess.ing`, `wisdominanutshell.academy`.
- Cloudflare token currently allows zone DNS reads/writes but returned `403` for account-level tunnels, Pages, Workers, R2, rulesets, and zone settings API calls.
- One Linux App Service plan, `ASP-aipodcastinggroup-aef6` (`P1mv3`), hosts 10 container apps with `alwaysOn=true`.
- Azure Front Door profile `ghost-front-door` routes several public hostnames to single App Service origins.
- DNS audit showed `adithyan.io`, `www.adithyan.io`, and `mindreader.adithyan.io` are Cloudflare-proxied directly to App Service, while `aipodcast.ing`, `app.aipodcast.ing`, `thoughtforms-life.aipodcast.ing`, and `podcast.futureoflife.org` are still served through Azure Front Door.
- User approved immediate cleanup for:
  - stale Front Door custom domains related to `adithyan.io` and `www.adithyan.io`;
  - stale/404 `blog.aipodcast.ing` and `cursorcast.aipodcast.ing` routing.

## Done When
- [ ] All active public hostnames have a documented owner, origin, DNS mode, and migration/keep decision.
- [ ] Azure Front Door is either fully removed or explicitly retained with documented justification.
- [ ] App Service plan cost is reduced by moving or retiring enough hosted apps to downsize/delete `P1mv3`.
- [ ] Low-risk cleanup candidates are removed or explicitly retained: stale Front Door domains/routes, unused DNS records, empty backup vaults, idle Redis, excess ACR storage, noisy logging.
- [ ] Every migration step has validation evidence recorded in this tracker or linked resources.
- [ ] Residual Azure dependencies are intentional and documented.

## Milestones
- [ ] Milestone 1 — Baseline inventory and safe cleanup. Acceptance: tracker exists, approved stale routing items are removed, and affected public hostnames still behave as expected or are intentionally absent. Validate: Azure Front Door route/domain listing, Cloudflare DNS listing, and `curl -I` public checks.
- [ ] Milestone 2 — Front Door replacement plan. Acceptance: every Front Door hostname has a proposed Cloudflare/App Service/Vercel/other target and rollback note. Validate: dry-run route map reviewed before DNS changes.
- [ ] Milestone 3 — Hostname-by-hostname Front Door migration. Acceptance: selected hostname is moved off Front Door with TLS, redirects, caching, and app behavior verified. Validate: DNS resolution, response headers, app smoke checks.
- [ ] Milestone 4 — App Service plan reduction. Acceptance: enough apps are migrated/retired to downsize or remove `P1mv3`. Validate: app request/error metrics and post-change cost trend.
- [ ] Milestone 5 — Backing service optimization. Acceptance: Redis, ACR, logs, backups, storage, and databases have keep/migrate/delete decisions with implemented low-risk changes. Validate: service-specific metrics and restore/rollback notes where relevant.

## Execution Rules
- Keep work scoped to the current milestone unless the tracker explicitly expands scope.
- Prefer read-only audit before mutation; mutate only items approved by the user or clearly marked safe in this tracker.
- Validate public hostname behavior before and after DNS or edge changes.
- Do not delete databases, storage accounts, backup-protected data, or app services without an explicit migration/backup step.
- Record Azure resource names, Cloudflare DNS records, and validation outputs in the progress log while details are fresh.
- Use `Current Batch` as the live execution board and primary resume point.
- Update this tracker before ending each work batch.

## Decisions
- Work will proceed slowly and hostname-by-hostname rather than as a big-bang Azure exit.
- Cloudflare should be the preferred public edge where feasible.
- Azure Front Door is a migration target because current configured routes use single App Service origins, not complex multi-origin load balancing.
- `adithyan.io`, `www.adithyan.io`, `blog.aipodcast.ing`, and `cursorcast.aipodcast.ing` cleanup is approved for the initial batch.

## Open Questions / Blockers
- Need broader Cloudflare API/OAuth access before auditing Pages, Workers, R2, account tunnels, rulesets, and zone settings through API.
- Confirm owner/desired future for `podcast.futureoflife.org`, which is outside the Cloudflare zones available to this token.

## Current Batch
| Status | Work Item | Role | Resource |
| --- | --- | --- | --- |
| in_progress | Remove approved stale Front Door custom domains and 404 DNS/routing records | parent | `resources/baseline-routing.md` |
| todo | Validate affected hostnames and checkpoint Milestone 1 progress | parent | `resources/baseline-routing.md` |

## Backlog / Remaining Work
- [ ] Create and maintain `resources/baseline-routing.md` with current Azure/Cloudflare route map and cleanup evidence.
- [ ] Build a full hostname ownership table for all Azure App Service, Front Door, Cloudflare, Vercel, and tunnel-backed hostnames.
- [ ] Decide whether to delete empty `ghost-backup-vault-lrs` after portal/CLI confirmation.
- [ ] Audit Redis callers and decide whether `aip-redis` can be removed, replaced, or left temporarily.
- [ ] Review ACR retention/storage and decide whether to downgrade from Standard or prune old images.
- [ ] Tune Log Analytics/App Insights ingestion if logs are noisy.
- [ ] Produce a Front Door migration runbook for one low-risk hostname.
- [ ] Execute Front Door migrations one hostname at a time.
- [ ] Review and finalize `learnings/README.md` before archiving this project.
- [ ] Archive the tracker when the Azure dependency reduction scope is complete or explicitly descoped.

## Validation / Test Plan
- Azure Front Door inventory: `az afd custom-domain list`, `az afd route list`, `az afd origin-group list`, `az afd origin list`.
- Cloudflare DNS inventory: Cloudflare API `zones/:id/dns_records` for available zones.
- Public smoke checks: `dig +short <hostname>` and `curl -ksSI https://<hostname>` before and after edge/DNS changes.
- Azure service metrics: `az monitor metrics list` for App Service plan/apps, Front Door, Redis, databases, Cosmos, and logging where relevant.
- Repo validation after tracker edits: `./scripts/check-agent-control-planes.sh` if control-plane files change; otherwise targeted markdown/file sanity checks are sufficient for project tracker-only edits.

## Progress Log
- 2026-05-29: [IN-PROGRESS] Created Azure exit project tracker and started approved Milestone 1 cleanup batch.
