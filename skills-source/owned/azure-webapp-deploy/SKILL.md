---
name: azure-webapp-deploy
description: Deploy small or production web apps to Azure App Service with Azure Container Registry, GitHub Actions OIDC, Key Vault-backed runtime settings, and optional Cloudflare custom domains. Use when asked to publish, deploy, create a Web App, add CI/CD, wire an Azure-hosted app, or point a domain/subdomain at an Azure Web App.
---

# Azure Web App Deploy

## Overview

Use this skill to help an agent deploy a web app through the house Azure pattern:
container image -> ACR -> Azure App Service -> optional Cloudflare hostname.

This is not a one-shot wizard. Work with the user in phases, ask for missing
choices, and use the scripts as independent noninteractive helpers.

## Interaction Model

- Ask the user for decisions that are not safely inferable.
- Do not invent a public domain name without user approval.
- Prefer a deployable default only when the repo or user has already provided a clear target.
- Keep scripts agent-first: JSON output, `--no-input`, dry-run/planning before state changes.
- Keep runtime secrets out of GitHub. Use Azure Key Vault references in App Service settings.

## Decisions To Gather

Before applying changes, know or confirm:

- GitHub repo, default branch, and deploy environment name.
- App name, resource group, App Service Plan, ACR name/login server, and image repository.
- Whether the app needs runtime secrets, especially LLM settings.
- Key Vault name and secret names for runtime settings.
- Health/status endpoints for deployment verification.
- Optional domain, DNS provider, Cloudflare zone, and whether the hostname should be proxied.

## Workflow

1. Inspect the repo:
   `python3 scripts/inspect_webapp_deploy.py --repo-dir <repo> --no-input`
2. Render a plan:
   `python3 scripts/render_plan.py --repo-dir <repo> --github-repo <owner/repo> ...`
3. Make repo changes:
   - Add or verify a Dockerfile.
   - Add or verify a GitHub Actions deploy workflow.
   - For Next.js, prefer standalone output for container deploys.
4. Configure GitHub/Azure:
   - GitHub repo/environment variables for Azure OIDC identifiers.
   - Azure federated credential matching the workflow subject.
   - Azure Web App on the chosen App Service Plan.
   - System-assigned identity, `AcrPull`, and Key Vault read role if needed.
5. Deploy and watch the workflow.
6. Configure optional Cloudflare hostname only after user confirms the domain.
7. Verify:
   `python3 scripts/verify_deploy.py --base-url https://<host> --path /api/health`

For exact command guidance, read `references/workflow.md`.

## LLM Runtime Pattern

If the deployed app calls an OpenAI-compatible endpoint:

- Prefer app env names such as `LLM_API_ENDPOINT`, `LLM_API_KEY`, `LLM_MODEL`, and
  `LLM_REASONING_EFFORT`.
- Set secret-like values in Azure App Service as Key Vault references.
- Do not put LLM API keys or endpoint-routing secrets in GitHub Actions secrets.
- Verify with a server-side endpoint such as `/api/openai/status?check=1` when present.

## Script Contract

The bundled scripts are independent helpers. They do not prompt, do not read
secret values, and default to JSON. See `references/script-contract.md`.

Available scripts:

- `scripts/inspect_webapp_deploy.py` checks repo readiness.
- `scripts/render_plan.py` prints a structured deploy/domain plan.
- `scripts/verify_deploy.py` checks deployed HTTP endpoints.

## Cloudflare Domains

For Cloudflare-backed custom hostnames, use the staged flow in
`references/cloudflare-domain.md`: DNS-only first, Azure verification, SNI
binding, then proxied CNAME.

## Guardrails

- Do not use publish profiles for new deployments unless OIDC is unavailable and the user accepts that tradeoff.
- Do not add broad GitHub secrets for runtime app config.
- Do not make private LLM or backend services public just to make deploys work.
- Do not leave the Azure app pointing at a nonexistent image without calling it out.
- Record durable deployment decisions in the repo after setup.
