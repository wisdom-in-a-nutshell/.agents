# Skills Registry

Single source of truth for skill classification and link distribution.

Policy:
- Origins: `external`, `owned`
- Distribution: `link` only
- Canonical sources live under `skills-source/<origin>/<skill>`
- Global runtime discovery lives under `skills/<skill>` as symlinks
- Repo-scoped skills live under `<repo>/.agents/skills/<skill>` as symlinks

<!-- managed-skills-table:start -->
| skill | origin | scope | repos | source_path | upstream_ref | notes |
| --- | --- | --- | --- | --- | --- | --- |
| agent-browser | external | global | * | /Users/dobby/.agents/skills-source/external/agent-browser | openai/skills:skills/.curated/agent-browser@main | global runtime |
| defuddle | external | global | * | /Users/dobby/.agents/skills-source/external/defuddle | openai/skills:skills/.curated/defuddle@main | global runtime |
| json-canvas | external | global | * | /Users/dobby/.agents/skills-source/external/json-canvas | openai/skills:skills/.curated/json-canvas@main | global runtime |
| obsidian-bases | external | global | * | /Users/dobby/.agents/skills-source/external/obsidian-bases | openai/skills:skills/.curated/obsidian-bases@main | global runtime |
| obsidian-cli | external | global | * | /Users/dobby/.agents/skills-source/external/obsidian-cli | openai/skills:skills/.curated/obsidian-cli@main | global runtime |
| obsidian-markdown | external | global | * | /Users/dobby/.agents/skills-source/external/obsidian-markdown | openai/skills:skills/.curated/obsidian-markdown@main | global runtime |
| agent-native-repo-playbook | owned | global | * | /Users/dobby/.agents/skills-source/owned/agent-native-repo-playbook | - | global runtime |
| project-executor | owned | global | * | /Users/dobby/.agents/skills-source/owned/project-executor | - | global runtime |
| project-planner | owned | global | * | /Users/dobby/.agents/skills-source/owned/project-planner | - | global runtime |
| vercel-react-best-practices | external | repo | adithyan-ai-videos,aipodcasting,aipodcasting-landing-page,aipodcasting-public-website,blog-personal | /Users/dobby/.agents/skills-source/external/vercel-react-best-practices | vercel-labs/agent-skills:skills/react-best-practices@main | shared repo skill |
| web-design-guidelines | external | repo | adithyan-ai-videos,aipodcasting,aipodcasting-landing-page,aipodcasting-public-website,blog-personal | /Users/dobby/.agents/skills-source/external/web-design-guidelines | vercel-labs/agent-skills:skills/web-design-guidelines@main | shared repo skill |
| openai-docs | external | repo | codexclaw | /Users/dobby/.agents/skills-source/external/openai-docs | openai/skills:skills/.curated/openai-docs@main | shared repo skill |
| pretty-mermaid | external | repo | codexclaw | /Users/dobby/.agents/skills-source/external/pretty-mermaid | local-import | promoted from repo-local |
| modal-function-sync | owned | repo | aipodcasting,modal_functions,win | /Users/dobby/.agents/skills-source/owned/modal-function-sync | - | shared repo skill |
| aip-dto-contract-sync | owned | repo | aipodcasting,win | /Users/dobby/.agents/skills-source/owned/aip-dto-contract-sync | - | shared repo skill |
| aip-frontend-contract-apply | owned | repo | aipodcasting,win | /Users/dobby/.agents/skills-source/owned/aip-frontend-contract-apply | - | shared repo skill |
| show-password-setup | owned | repo | aipodcasting,win | /Users/dobby/.agents/skills-source/owned/show-password-setup | - | shared repo skill |
| azure-webapp-config | owned | repo | aipodcasting,aipodcasting-public-website,win | /Users/dobby/.agents/skills-source/owned/azure-webapp-config | - | shared repo skill |
<!-- managed-skills-table:end -->

## Repo-Local Skills (Unmanaged)

These stay only in their repos and are intentionally not linked from this registry.

| repo | skill | notes |
| --- | --- | --- |
| adithyan-ai-videos | creating-video | repo-local |
| adithyan-ai-videos | remotion | repo-local |
| aipodcasting-public-website | designer-workflow | repo-local |
| aipodcasting-public-website | visual-audit-loop | repo-local |
| aipodcasting-public-website | workflow-visual-audit | repo-local |
| blog-personal | blog-posting | repo-local |
| codexclaw | codex-app-server | repo-local |
| codexclaw | ios-mobile-gateway-workflow | repo-local |
| modal_functions | modal-function-intake | repo-local |
| win | add-env-var | repo-local |
| win | channel-create | repo-local |
| win | contact-form-automation | repo-local |
| win | descript-api-docs-sync | repo-local |
| win | log-investigation | repo-local |
| win | scheduled-jobs | repo-local |
