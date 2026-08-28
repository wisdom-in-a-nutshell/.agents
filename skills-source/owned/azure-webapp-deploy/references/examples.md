# Examples

These examples are illustrative. Confirm values with the user before applying.

## Flexible Plan

```bash
python3 ~/GitHub/agents/skills-source/owned/azure-webapp-deploy/scripts/render_plan.py \
  --repo-dir ~/GitHub/my-app \
  --github-repo owner/my-app \
  --app-name my-app-demo \
  --resource-group ghost \
  --app-service-plan-id /subscriptions/.../serverfarms/ASP-example \
  --acr-name aipodcasting \
  --acr-login-server aipodcasting.azurecr.io \
  --image-name my-app-demo \
  --health-path /api/health \
  --no-input
```

## LLM Runtime Plan

```bash
python3 ~/GitHub/agents/skills-source/owned/azure-webapp-deploy/scripts/render_plan.py \
  --repo-dir ~/GitHub/my-llm-app \
  --github-repo owner/my-llm-app \
  --app-name my-llm-app \
  --resource-group ghost \
  --app-service-plan-id /subscriptions/.../serverfarms/ASP-example \
  --acr-name aipodcasting \
  --acr-login-server aipodcasting.azurecr.io \
  --image-name my-llm-app \
  --llm \
  --status-path /api/openai/status?check=1 \
  --no-input
```
