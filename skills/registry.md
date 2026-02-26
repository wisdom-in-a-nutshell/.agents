# Skills Registry

Generated from `skills/registry.json`. Edit JSON only.

Policy:
- Origins: `external`, `owned`
- Distribution: `link` only
- Canonical sources live under `skills-source/<origin>/<skill>`
- Global runtime discovery lives under `skills/<skill>` as symlinks
- Repo-scoped skills live under `<repo>/.agents/skills/<skill>` as symlinks

## Managed Skills

| skill | origin | scope | repos | source_path | upstream_ref |
| --- | --- | --- | --- | --- | --- |
| agent-browser | external | global | * | skills-source/external/agent-browser | vercel-labs/agent-browser:skills/agent-browser@main |
| defuddle | external | global | * | skills-source/external/defuddle | kepano/obsidian-skills:skills/defuddle@main |
| json-canvas | external | global | * | skills-source/external/json-canvas | kepano/obsidian-skills:skills/json-canvas@main |
| obsidian-bases | external | global | * | skills-source/external/obsidian-bases | kepano/obsidian-skills:skills/obsidian-bases@main |
| obsidian-cli | external | global | * | skills-source/external/obsidian-cli | kepano/obsidian-skills:skills/obsidian-cli@main |
| obsidian-markdown | external | global | * | skills-source/external/obsidian-markdown | kepano/obsidian-skills:skills/obsidian-markdown@main |
| agent-native-repo-playbook | owned | global | * | skills-source/owned/agent-native-repo-playbook | - |
| client-interface-guidelines | owned | global | * | skills-source/owned/client-interface-guidelines | - |
| project-executor | owned | global | * | skills-source/owned/project-executor | - |
| project-planner | owned | global | * | skills-source/owned/project-planner | - |
| vercel-react-best-practices | external | repo | adithyan-ai-videos,aipodcasting,aipodcasting-landing-page,aipodcasting-public-website,blog-personal | skills-source/external/vercel-react-best-practices | vercel-labs/agent-skills:skills/react-best-practices@main |
| web-design-guidelines | external | repo | adithyan-ai-videos,aipodcasting,aipodcasting-landing-page,aipodcasting-public-website,blog-personal | skills-source/external/web-design-guidelines | vercel-labs/agent-skills:skills/web-design-guidelines@main |
| openai-docs | external | repo | codexclaw | skills-source/external/openai-docs | openai/skills:skills/.curated/openai-docs@main |
| pretty-mermaid | owned | repo | codexclaw | skills-source/owned/pretty-mermaid | - |
| modal-function-sync | owned | repo | aipodcasting,modal_functions,win | skills-source/owned/modal-function-sync | - |
| aip-dto-contract-sync | owned | repo | aipodcasting,win | skills-source/owned/aip-dto-contract-sync | - |
| aip-frontend-contract-apply | owned | repo | aipodcasting,win | skills-source/owned/aip-frontend-contract-apply | - |
| show-password-setup | owned | repo | aipodcasting,win | skills-source/owned/show-password-setup | - |
| azure-webapp-config | owned | repo | aipodcasting,aipodcasting-public-website,win | skills-source/owned/azure-webapp-config | - |

## Repo-Local Skills (Unmanaged)

| repo | skill |
| --- | --- |
| adithyan-ai-videos | creating-video |
| adithyan-ai-videos | remotion |
| aipodcasting-public-website | designer-workflow |
| aipodcasting-public-website | visual-audit-loop |
| aipodcasting-public-website | workflow-visual-audit |
| blog-personal | blog-posting |
| codexclaw | codex-app-server |
| codexclaw | ios-mobile-gateway-workflow |
| modal_functions | modal-function-intake |
| win | add-env-var |
| win | channel-create |
| win | contact-form-automation |
| win | descript-api-docs-sync |
| win | log-investigation |
| win | scheduled-jobs |
