#!/usr/bin/env python3
"""Render a structured Azure Web App deployment plan without changing state."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _result(status: str, data: dict[str, Any], error: dict[str, Any] | None, start: float) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "render_plan",
        "status": status,
        "data": data,
        "error": error,
        "meta": {
            "request_id": str(uuid.uuid4()),
            "timestamp_utc": _now(),
            "duration_ms": int((time.monotonic() - start) * 1000),
        },
    }


def _missing(args: argparse.Namespace) -> list[str]:
    required = [
        "repo_dir",
        "github_repo",
        "app_name",
        "resource_group",
        "app_service_plan_id",
        "acr_name",
        "acr_login_server",
        "image_name",
    ]
    missing = [name for name in required if not getattr(args, name)]
    if args.llm:
        for name in ["key_vault_name", "llm_endpoint_secret", "llm_key_secret"]:
            if not getattr(args, name):
                missing.append(name)
    if args.domain:
        if not (args.cloudflare_zone_id or args.cloudflare_zone_name):
            missing.append("cloudflare_zone_id_or_name")
    return missing


def _step(step_id: str, title: str, state_change: bool, commands: list[str], notes: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "state_change": state_change,
        "commands": commands,
        "notes": notes or [],
    }


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    repo_dir = str(Path(args.repo_dir).expanduser()) if args.repo_dir else None
    subject = f"repo:{args.github_repo}:environment:{args.environment}" if args.github_repo else None
    image_ref = (
        f"{args.acr_login_server}/{args.image_name}:${{GITHUB_SHA}}"
        if args.acr_login_server and args.image_name
        else None
    )

    steps = [
        _step(
            "repo-inspect",
            "Inspect repo and confirm deploy readiness",
            False,
            [
                "python3 ~/GitHub/agents/skills-source/owned/azure-webapp-deploy/scripts/inspect_webapp_deploy.py "
                f"--repo-dir {repo_dir or '<repo-dir>'} --no-input"
            ],
        ),
        _step(
            "repo-files",
            "Add or verify Dockerfile, standalone build config, and GitHub Actions workflow",
            True,
            [],
            ["Use repo patterns first. For Next.js, prefer output: standalone."],
        ),
        _step(
            "github-oidc",
            "Configure GitHub repo variables and Azure federated credential",
            True,
            [
                f"gh variable set AZURE_CLIENT_ID --repo {args.github_repo or '<owner/repo>'} --body <client-id>",
                f"gh variable set AZURE_TENANT_ID --repo {args.github_repo or '<owner/repo>'} --body <tenant-id>",
                f"gh variable set AZURE_SUBSCRIPTION_ID --repo {args.github_repo or '<owner/repo>'} --body <subscription-id>",
                f"az ad app federated-credential create --id <client-id> --parameters <json-with-subject-{subject or '<subject>'}>",
            ],
            ["Check existing federated credentials before creating a new one."],
        ),
        _step(
            "azure-webapp",
            "Create/configure Azure Web App and identity",
            True,
            [
                "az webapp create "
                f"--resource-group {args.resource_group or '<resource-group>'} "
                f"--plan {args.app_service_plan_id or '<app-service-plan-id>'} "
                f"--name {args.app_name or '<app-name>'} "
                f"--deployment-container-image-name {args.acr_login_server or '<acr-login-server>'}/{args.image_name or '<image-name>'}:latest",
                f"az webapp identity assign -g {args.resource_group or '<resource-group>'} -n {args.app_name or '<app-name>'}",
                "az role assignment create --assignee <principal-id> --role AcrPull --scope <acr-id>",
            ],
        ),
        _step(
            "runtime-settings",
            "Set runtime app settings",
            True,
            [],
            ["Use Key Vault references for secret-like settings."],
        ),
        _step(
            "deploy",
            "Run and watch GitHub Actions deployment",
            True,
            [
                f"gh run list --repo {args.github_repo or '<owner/repo>'} --limit 5",
                f"gh run watch <run-id> --repo {args.github_repo or '<owner/repo>'} --interval 10 --exit-status",
            ],
            [f"Expected image: {image_ref or '<acr-login-server>/<image-name>:<sha>'}"],
        ),
        _step(
            "verify",
            "Verify deployed app",
            False,
            [
                "python3 ~/GitHub/agents/skills-source/owned/azure-webapp-deploy/scripts/verify_deploy.py "
                f"--base-url https://{args.app_name or '<app-name>'}.azurewebsites.net "
                f"--path {args.health_path}"
            ],
        ),
    ]

    if args.llm:
        steps[4]["commands"].extend(
            [
                "az role assignment create --assignee <principal-id> --role 'Key Vault Secrets User' --scope <key-vault-id>",
                "az webapp config appsettings set "
                f"-g {args.resource_group or '<resource-group>'} -n {args.app_name or '<app-name>'} --settings "
                f"LLM_API_ENDPOINT=@Microsoft.KeyVault(SecretUri=https://{args.key_vault_name or '<vault>'}.vault.azure.net/secrets/{args.llm_endpoint_secret or '<endpoint-secret>'}/) "
                f"LLM_API_KEY=@Microsoft.KeyVault(SecretUri=https://{args.key_vault_name or '<vault>'}.vault.azure.net/secrets/{args.llm_key_secret or '<key-secret>'}/)",
            ]
        )
    if args.domain:
        steps.append(
            _step(
                "domain",
                "Configure optional Cloudflare custom hostname",
                True,
                [
                    f"Create DNS-only CNAME {args.domain} -> {args.app_name or '<app-name>'}.azurewebsites.net",
                    f"Create TXT asuid.{args.domain} -> <customDomainVerificationId>",
                    "az webapp config hostname add "
                    f"--resource-group {args.resource_group or '<resource-group>'} "
                    f"--webapp-name {args.app_name or '<app-name>'} --hostname {args.domain}",
                    "Bind SNI cert, then switch Cloudflare CNAME to proxied if desired.",
                ],
                ["See references/cloudflare-domain.md before applying."],
            )
        )

    missing = _missing(args)
    return {
        "plan_state": "needs_input" if missing else "ready",
        "missing_decisions": missing,
        "target": {
            "repo_dir": repo_dir,
            "github_repo": args.github_repo,
            "environment": args.environment,
            "app_name": args.app_name,
            "resource_group": args.resource_group,
            "app_service_plan_id": args.app_service_plan_id,
            "acr_name": args.acr_name,
            "acr_login_server": args.acr_login_server,
            "image_name": args.image_name,
            "domain": args.domain,
            "cloudflare_zone": args.cloudflare_zone_id or args.cloudflare_zone_name,
            "llm_enabled": args.llm,
        },
        "steps": steps,
    }


def main() -> int:
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir")
    parser.add_argument("--github-repo")
    parser.add_argument("--environment", default="Production")
    parser.add_argument("--app-name")
    parser.add_argument("--resource-group")
    parser.add_argument("--app-service-plan-id")
    parser.add_argument("--acr-name")
    parser.add_argument("--acr-login-server")
    parser.add_argument("--image-name")
    parser.add_argument("--health-path", default="/api/health")
    parser.add_argument("--status-path", action="append", default=[])
    parser.add_argument("--domain")
    parser.add_argument("--cloudflare-zone-name")
    parser.add_argument("--cloudflare-zone-id")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--key-vault-name")
    parser.add_argument("--llm-endpoint-secret")
    parser.add_argument("--llm-key-secret")
    parser.add_argument("--json", action="store_true", help="Emit JSON. This is the default.")
    parser.add_argument("--plain", action="store_true", help="Emit concise plain text.")
    parser.add_argument("--no-input", action="store_true", help="Do not prompt. This script never prompts.")
    args = parser.parse_args()

    data = build_plan(args)
    result = _result("ok", data, None, start)

    if args.plain:
        print(f"plan_state: {data['plan_state']}")
        if data["missing_decisions"]:
            print("missing: " + ", ".join(data["missing_decisions"]))
        for step in data["steps"]:
            print(f"- {step['id']}: {step['title']}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
