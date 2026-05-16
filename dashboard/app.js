const AUTO_REFRESH_MS = 5 * 60 * 1000;

const state = {
  data: null,
  section: "overview",
  filter: "all",
  loadError: null,
  loading: false,
  sidebarCollapsed: localStorage.getItem("agentControlSidebarCollapsed") === "true",
};

const els = {
  sidebarToggle: document.querySelector("#sidebarToggle"),
  lastUpdated: document.querySelector("#lastUpdated"),
  refreshStatus: document.querySelector("#refreshStatus"),
  searchInput: document.querySelector("#searchInput"),
  sectionEyebrow: document.querySelector("#sectionEyebrow"),
  sectionTitle: document.querySelector("#sectionTitle"),
  metricsGrid: document.querySelector("#metricsGrid"),
  warningPanel: document.querySelector("#warningPanel"),
  warningList: document.querySelector("#warningList"),
  warningCount: document.querySelector("#warningCount"),
  filterBar: document.querySelector("#filterBar"),
  contentRegion: document.querySelector("#contentRegion"),
  navCountOverview: document.querySelector("#navCountOverview"),
  navCountRepos: document.querySelector("#navCountRepos"),
  navCountSkills: document.querySelector("#navCountSkills"),
  navCountPlugins: document.querySelector("#navCountPlugins"),
  navCountMcp: document.querySelector("#navCountMcp"),
  navCountHooks: document.querySelector("#navCountHooks"),
};

const sections = {
  overview: {
    eyebrow: "Overview",
    title: "Control-plane status",
  },
  repos: {
    eyebrow: "Repos",
    title: "Managed repo map",
  },
  skills: {
    eyebrow: "Skills",
    title: "Skill availability",
  },
  plugins: {
    eyebrow: "Plugins",
    title: "Codex plugin state",
  },
  mcp: {
    eyebrow: "MCP",
    title: "MCP presets",
  },
  hooks: {
    eyebrow: "Hooks",
    title: "Lifecycle hooks",
  },
};

const filterOptions = {
  overview: [{ id: "all", label: "All" }],
  repos: [
    { id: "all", label: "All" },
    { id: "repo-skills", label: "Repo skills" },
    { id: "repo-plugins", label: "Repo plugins" },
    { id: "repo-mcp", label: "Repo MCP" },
    { id: "custom", label: "Custom config" },
  ],
  skills: [
    { id: "all", label: "All" },
    { id: "global", label: "Global" },
    { id: "repo", label: "Repo scoped" },
    { id: "repo-local", label: "Repo local" },
    { id: "owned", label: "Owned" },
    { id: "external", label: "External" },
    { id: "dormant", label: "Dormant" },
  ],
  plugins: [
    { id: "all", label: "All" },
    { id: "enabled", label: "Enabled" },
    { id: "disabled", label: "Disabled" },
    { id: "global", label: "Global" },
    { id: "repo", label: "Repo scoped" },
    { id: "repo-local", label: "Repo local" },
  ],
  mcp: [
    { id: "all", label: "All" },
    { id: "global", label: "Global" },
    { id: "repo", label: "Repo" },
    { id: "plugin", label: "Plugin" },
    { id: "unassigned", label: "Unassigned" },
  ],
  hooks: [
    { id: "all", label: "All" },
    { id: "enabled", label: "Enabled" },
    { id: "disabled", label: "Disabled" },
    { id: "global", label: "Global" },
    { id: "repo", label: "Repo scoped" },
  ],
};

async function loadData(options = {}) {
  if (state.loading) {
    return;
  }
  state.loading = true;
  if (!options.background) {
    els.refreshStatus.textContent = "Updating";
  }
  try {
    const response = await fetch("/api/control-plane", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }
    state.data = await response.json();
    state.loadError = null;
    render();
  } catch (error) {
    if (state.data && options.background) {
      els.refreshStatus.textContent = "Auto-refresh failed";
      return;
    }
    state.loadError = error;
    render();
  } finally {
    state.loading = false;
  }
}

function render() {
  if (state.loadError) {
    renderLoadError(state.loadError);
    return;
  }
  if (!state.data) {
    return;
  }

  updateChrome();
  renderHeader();
  renderMetrics();
  renderWarnings();
  renderFilters();
  renderActiveSection();
}

function updateChrome() {
  const { counts, generated_at_utc: generatedAt } = state.data;
  els.lastUpdated.textContent = `Updated ${formatDate(generatedAt)}`;
  els.refreshStatus.textContent = "Auto-refresh every 5m";
  els.navCountOverview.textContent = counts.items;
  els.navCountRepos.textContent = counts.repos;
  els.navCountSkills.textContent = counts.skills;
  els.navCountPlugins.textContent = counts.plugins;
  els.navCountMcp.textContent = counts.mcp;
  els.navCountHooks.textContent = counts.hooks;
}

function renderHeader() {
  const meta = sections[state.section] || sections.overview;
  els.sectionEyebrow.textContent = meta.eyebrow;
  els.sectionTitle.textContent = meta.title;
}

function renderMetrics() {
  els.metricsGrid.replaceChildren();
  metricsForSection(state.section).forEach((metric) => {
    const block = createElement("article", `metric-block ${metric.tone || ""}`);
    block.append(
      createElement("span", "", metric.label),
      createElement("strong", "", String(metric.value)),
    );
    els.metricsGrid.append(block);
  });
}

function metricsForSection(section) {
  const groups = state.data.groups;
  const counts = state.data.counts;
  if (section === "skills") {
    return [
      metric("Global", countItems(groups.skills, (item) => item.scope === "global")),
      metric("Repo scoped", countItems(groups.skills, (item) => item.scope === "repo")),
      metric("Repo local", countItems(groups.skills, (item) => item.scope === "repo-local")),
      metric("Owned", countItems(groups.skills, (item) => item.details.origin === "owned")),
      metric("External", countItems(groups.skills, (item) => item.details.origin === "external")),
    ];
  }
  if (section === "plugins") {
    return [
      metric("Enabled", countItems(groups.plugins, (item) => item.status === "enabled")),
      metric("Disabled", countItems(groups.plugins, (item) => item.status === "disabled"), "warning"),
      metric("Global", countItems(groups.plugins, (item) => item.scope === "global")),
      metric("Repo scoped", countItems(groups.plugins, (item) => item.scope === "repo")),
      metric("Repo local", countItems(groups.plugins, (item) => item.scope === "repo-local")),
    ];
  }
  if (section === "mcp") {
    return [
      metric("Global", countItems(groups.mcp, (item) => scopeHas(item, "global"))),
      metric("Repo", countItems(groups.mcp, (item) => scopeHas(item, "repo"))),
      metric("Plugin", countItems(groups.mcp, (item) => scopeHas(item, "plugin"))),
      metric("Unassigned", countItems(groups.mcp, (item) => item.scope === "unassigned"), "warning"),
    ];
  }
  if (section === "repos") {
    return [
      metric("Managed", groups.repos.length),
      metric("Repo skills", countItems(groups.repos, (repo) => repoScopedSkillsForRepo(repo).length)),
      metric("Repo plugins", countItems(groups.repos, (repo) => repoScopedPluginsForRepo(repo).length)),
      metric("Repo MCP", countItems(groups.repos, (repo) => repoDirectMcpForRepo(repo).length)),
      metric("Warnings", counts.warnings, counts.warnings ? "warning" : ""),
    ];
  }
  if (section === "hooks") {
    return [
      metric("Enabled", countItems(groups.hooks, (item) => item.status === "enabled")),
      metric("Disabled", countItems(groups.hooks, (item) => item.status === "disabled"), "warning"),
      metric("Global", countItems(groups.hooks, (item) => item.scope === "global")),
      metric("Repo scoped", countItems(groups.hooks, (item) => item.scope === "repo")),
    ];
  }
  return [
    metric("Repos", counts.repos),
    metric("Skills", counts.skills),
    metric("Plugins", counts.plugins),
    metric("MCP", counts.mcp),
    metric("Warnings", counts.warnings, counts.warnings ? "warning" : ""),
  ];
}

function metric(label, value, tone = "") {
  return { label, value, tone };
}

function renderWarnings() {
  const warnings = state.data.warnings;
  els.warningList.replaceChildren();
  els.warningCount.textContent = warnings.length;
  els.warningPanel.classList.toggle("hidden", warnings.length === 0);
  warnings.slice(0, 8).forEach((warning) => {
    const item = createElement("div", `warning-item ${warning.severity === "error" ? "error" : ""}`);
    item.append(
      createElement("strong", "", warning.message),
      createElement("span", "", `${warning.code} / ${warning.source}`),
    );
    els.warningList.append(item);
  });
}

function renderFilters() {
  els.filterBar.replaceChildren();
  const options = filterOptions[state.section] || filterOptions.overview;
  const visibleOptions = options.filter((option) => option.id === "all" || countForFilter(state.section, option.id) > 0);
  if (visibleOptions.length <= 1) {
    els.filterBar.classList.add("hidden");
    state.filter = "all";
    return;
  }
  els.filterBar.classList.remove("hidden");
  if (!visibleOptions.some((option) => option.id === state.filter)) {
    state.filter = "all";
  }
  visibleOptions.forEach((option) => {
    const button = createElement("button", `filter-chip ${state.filter === option.id ? "active" : ""}`);
    button.type = "button";
    button.dataset.filter = option.id;
    button.append(
      createElement("span", "", option.label),
      createElement("strong", "", String(countForFilter(state.section, option.id))),
    );
    button.addEventListener("click", () => {
      state.filter = option.id;
      render();
    });
    els.filterBar.append(button);
  });
}

function countForFilter(section, filter) {
  if (section === "repos") {
    return filterRepos(state.data.groups.repos, filter, false).length;
  }
  const kind = section === "mcp" ? "mcp" : section;
  const items = state.data.groups[kind] || [];
  if (filter === "all") {
    return items.length;
  }
  return items.filter((item) => itemPassesFilter(item, section, filter)).length;
}

function renderActiveSection() {
  els.contentRegion.replaceChildren();
  if (state.section === "overview") {
    renderOverview();
  } else if (state.section === "repos") {
    renderRepos();
  } else if (state.section === "skills") {
    renderSkills();
  } else if (state.section === "plugins") {
    renderPlugins();
  } else if (state.section === "mcp") {
    renderMcp();
  } else if (state.section === "hooks") {
    renderHooks();
  }
}

function renderOverview() {
  const summary = createElement("section", "overview-grid");
  summary.append(
    overviewPanel("Global base kit", [
      statLine("Skills", globalSkills().length),
      statLine("Plugins", enabledGlobalPlugins().length),
      statLine("Hooks", enabledGlobalHooks().length),
      statLine("MCP", globalMcp().length),
    ]),
    overviewPanel("Repo-specific additions", [
      statLine("Repos with skills", countItems(state.data.groups.repos, (repo) => repoScopedSkillsForRepo(repo).length)),
      statLine("Repos with plugins", countItems(state.data.groups.repos, (repo) => repoScopedPluginsForRepo(repo).length)),
      statLine("Repos with MCP", countItems(state.data.groups.repos, (repo) => repoDirectMcpForRepo(repo).length)),
      statLine("Repo-local skills", countItems(state.data.groups.skills, (item) => item.scope === "repo-local")),
    ]),
    overviewPanel("Attention", attentionLines()),
  );
  els.contentRegion.append(summary);

  const repoRows = filteredRepos().slice(0, 8);
  els.contentRegion.append(
    groupedPanel("Repos with the most local shape", repoRows, repoOverviewRow, "No repos match this search."),
  );
}

function attentionLines() {
  const disabledPlugins = countItems(state.data.groups.plugins, (item) => item.status === "disabled");
  const disabledHooks = countItems(state.data.groups.hooks, (item) => item.status === "disabled");
  const unassignedMcp = countItems(state.data.groups.mcp, (item) => item.scope === "unassigned");
  return [
    statLine("Warnings", state.data.counts.warnings),
    statLine("Disabled plugins", disabledPlugins),
    statLine("Disabled hooks", disabledHooks),
    statLine("Unassigned MCP", unassignedMcp),
  ];
}

function overviewPanel(title, lines) {
  const panel = createElement("section", "overview-panel");
  panel.append(createElement("h2", "", title));
  const list = createElement("div", "stat-list");
  lines.forEach((line) => list.append(line));
  panel.append(list);
  return panel;
}

function statLine(label, value) {
  const row = createElement("div", "stat-line");
  row.append(createElement("span", "", label), createElement("strong", "", String(value)));
  return row;
}

function repoOverviewRow(repo) {
  const caps = repoCapabilitySummary(repo);
  const row = createElement("article", "compact-row repo-overview-row");
  const main = createEntityMain(repo.name, repo.details.path || repo.name);
  const totals = createElement("div", "mini-totals");
  totals.append(
    smallCount("Base", caps.baseTotal),
    smallCount("Local", caps.localTotal),
    smallCount("MCP", caps.directMcp.length),
  );
  row.append(main, totals);
  return row;
}

function renderRepos() {
  const repos = filteredRepos();
  if (!repos.length) {
    els.contentRegion.append(emptyState("No repos match this view."));
    return;
  }

  const list = createElement("div", "repo-list-view");
  repos.forEach((repo) => list.append(repoCard(repo)));
  els.contentRegion.append(list);
}

function repoCard(repo) {
  const caps = repoCapabilitySummary(repo);
  const card = createElement("article", "repo-card");

  const head = createElement("div", "repo-card-head");
  const title = createEntityMain(repo.name, repo.details.path || repo.name);
  const meta = createElement("div", "repo-runtime");
  meta.append(
    runtimePill(repo.details.model || "default model"),
    runtimePill(`reasoning ${repo.details.reasoning || "default"}`),
  );
  head.append(title, meta);

  const base = createElement("div", "base-kit");
  base.append(
    smallCount("Global skills", caps.globalSkills.length),
    smallCount("Global plugins", caps.globalPlugins.length),
    smallCount("Global hooks", caps.globalHooks.length),
    smallCount("Global MCP", caps.globalMcp.length),
  );

  const grid = createElement("div", "capability-grid");
  grid.append(
    capabilityBlock("Repo skills", caps.repoSkills, "skill", "Base only"),
    capabilityBlock("Repo plugins", caps.repoPlugins, "plugin", "None"),
    capabilityBlock("MCP", caps.directMcp, "mcp", "None"),
    capabilityBlock("Repo hooks", caps.repoHooks, "hook", "Global only"),
  );

  card.append(head, base, grid);
  return card;
}

function renderSkills() {
  const items = filteredItems("skills");
  const groups = [
    ["Global skills", items.filter((item) => item.scope === "global")],
    ["Repo-scoped skills", items.filter((item) => item.scope === "repo")],
    ["Repo-local skills", items.filter((item) => item.scope === "repo-local")],
    ["Dormant skills", items.filter((item) => item.status === "dormant")],
  ];
  renderPanels(groups, skillRow, "No skills match this view.");
}

function skillRow(item) {
  const row = createElement("article", "entity-row");
  const sourcePath = item.details.source_path || item.details.repo || "";
  const main = createEntityMain(item.title, compact([titleCase(item.details.origin), labelForScope(item), item.status]).join(" / "));
  if (sourcePath) {
    main.append(createElement("p", "entity-path", sourcePath));
  }
  row.append(main, availabilityBlock(item), rowActions(item));
  return row;
}

function renderPlugins() {
  const items = filteredItems("plugins");
  const groups = [
    ["Enabled global plugins", items.filter((item) => item.scope === "global" && item.status === "enabled")],
    ["Repo-scoped plugins", items.filter((item) => item.scope === "repo")],
    ["Repo-local plugins", items.filter((item) => item.scope === "repo-local")],
    ["Disabled plugins", items.filter((item) => item.status === "disabled")],
  ];
  renderPanels(groups, pluginRow, "No plugins match this view.");
}

function pluginRow(item) {
  const row = createElement("article", "entity-row");
  const meta = compact([item.details.marketplace, item.details.category, labelForScope(item), item.status]).join(" / ");
  row.append(createEntityMain(item.title, meta), availabilityBlock(item), rowActions(item));
  return row;
}

function renderMcp() {
  const items = filteredItems("mcp");
  const groups = [
    ["Global MCP presets", items.filter((item) => scopeHas(item, "global"))],
    ["Repo MCP presets", items.filter((item) => !scopeHas(item, "global") && scopeHas(item, "repo"))],
    ["Plugin MCP presets", items.filter((item) => !scopeHas(item, "global") && !scopeHas(item, "repo") && scopeHas(item, "plugin"))],
    ["Unassigned MCP definitions", items.filter((item) => item.scope === "unassigned")],
  ];
  renderPanels(groups, mcpRow, "No MCP presets match this view.");
}

function mcpRow(item) {
  const row = createElement("article", "entity-row mcp-row");
  const meta = compact([item.details.transport, item.details.url]).join(" / ") || item.status;
  row.append(createEntityMain(item.title, meta), mcpAvailabilityBlock(item), rowActions(item));
  return row;
}

function renderHooks() {
  const items = filteredItems("hooks");
  const groups = [
    ["Global hooks", items.filter((item) => item.scope === "global")],
    ["Repo hooks", items.filter((item) => item.scope === "repo")],
    ["Disabled hooks", items.filter((item) => item.status === "disabled")],
  ];
  renderPanels(groups, hookRow, "No hooks match this view.");
}

function hookRow(item) {
  const row = createElement("article", "entity-row");
  const runtimes = cleanArray(item.details.runtimes).join(", ");
  const meta = compact([item.details.event, runtimes, item.details.timeout ? `${item.details.timeout}s` : ""]).join(" / ");
  row.append(createEntityMain(item.title, meta), availabilityBlock(item), rowActions(item));
  return row;
}

function renderPanels(groups, renderer, emptyMessage) {
  let rendered = 0;
  groups.forEach(([title, items]) => {
    if (!items.length) {
      return;
    }
    els.contentRegion.append(groupedPanel(title, items, renderer, emptyMessage));
    rendered += items.length;
  });
  if (!rendered) {
    els.contentRegion.append(emptyState(emptyMessage));
  }
}

function groupedPanel(title, items, renderer, emptyMessage) {
  const panel = createElement("section", "section-panel");
  const heading = createElement("div", "panel-heading");
  heading.append(createElement("h2", "", title), createElement("span", "", String(items.length)));
  const rows = createElement("div", "row-stack");
  if (items.length) {
    items.forEach((item) => rows.append(renderer(item)));
  } else {
    rows.append(emptyState(emptyMessage));
  }
  panel.append(heading, rows);
  return panel;
}

function createEntityMain(title, subtitle) {
  const main = createElement("div", "entity-main");
  main.append(createElement("h3", "", title));
  if (subtitle) {
    main.append(createElement("p", "", subtitle));
  }
  return main;
}

function availabilityBlock(item) {
  const wrap = createElement("div", "availability-block");
  if (item.scope === "global") {
    wrap.append(createChip("All repos", item.kind));
    return wrap;
  }
  if (item.status === "dormant" || item.scope === "dormant") {
    wrap.append(createChip("Dormant", "warning"));
    return wrap;
  }
  const repos = cleanArray(item.repos);
  if (!repos.length) {
    wrap.append(createElement("span", "muted", "No repo assignment"));
    return wrap;
  }
  appendChips(wrap, repos.map(repoDisplayName), item.kind);
  return wrap;
}

function mcpAvailabilityBlock(item) {
  const wrap = createElement("div", "availability-block");
  if (scopeHas(item, "global")) {
    wrap.append(createChip("Global", "mcp"));
  }
  appendChips(wrap, cleanArray(item.repos).map(repoDisplayName), "repo");
  appendChips(wrap, cleanArray(item.details.plugins).map((plugin) => `Plugin: ${plugin}`), "plugin");
  if (!wrap.childElementCount) {
    wrap.append(createChip("Unassigned", "warning"));
  }
  return wrap;
}

function rowActions(item) {
  const actions = createElement("div", "row-actions");
  const link = createElement("a", "", sourceLabel(item));
  link.href = sourceHref(item);
  link.target = "_blank";
  link.rel = "noreferrer";
  actions.append(link);
  return actions;
}

function sourceHref(item) {
  if (item.kind === "skill" && item.details.source_path) {
    return `/source/${item.details.source_path}/SKILL.md`;
  }
  return `/source/${item.source}`;
}

function sourceLabel(item) {
  return item.kind === "skill" && item.details.source_path ? "SKILL.md" : "Registry";
}

function capabilityBlock(title, items, tone, emptyText) {
  const block = createElement("section", "capability-block");
  const heading = createElement("div", "capability-heading");
  heading.append(createElement("h3", "", title), createElement("strong", "", String(items.length)));
  const chips = createElement("div", "chip-list");
  if (items.length) {
    appendChips(chips, items.map((item) => item.title || item.name), tone);
  } else {
    chips.append(createElement("span", "muted", emptyText));
  }
  block.append(heading, chips);
  return block;
}

function smallCount(label, value) {
  const item = createElement("span", "small-count");
  item.append(createElement("span", "", label), createElement("strong", "", String(value)));
  return item;
}

function runtimePill(text) {
  return createElement("span", "runtime-pill", text);
}

function createChip(text, tone = "") {
  return createElement("span", `chip ${tone}`, text);
}

function appendChips(parent, values, tone) {
  values.forEach((value) => parent.append(createChip(value, tone)));
}

function filteredItems(groupName) {
  const items = state.data.groups[groupName] || [];
  return items.filter((item) => itemPassesFilter(item, groupName, state.filter) && itemMatchesQuery(item));
}

function filteredRepos() {
  return filterRepos(state.data.groups.repos, state.filter, true);
}

function filterRepos(repos, filter, includeQuery) {
  return repos.filter((repo) => {
    if (filter === "repo-skills" && !repoScopedSkillsForRepo(repo).length) {
      return false;
    }
    if (filter === "repo-plugins" && !repoScopedPluginsForRepo(repo).length) {
      return false;
    }
    if (filter === "repo-mcp" && !repoDirectMcpForRepo(repo).length) {
      return false;
    }
    if (filter === "custom" && !repoHasCustomConfig(repo)) {
      return false;
    }
    if (includeQuery && !repoMatchesQuery(repo)) {
      return false;
    }
    return true;
  });
}

function itemPassesFilter(item, section, filter) {
  if (filter === "all") {
    return true;
  }
  if (section === "skills") {
    if (filter === "owned" || filter === "external") {
      return item.details.origin === filter;
    }
    if (filter === "dormant") {
      return item.status === "dormant" || item.scope === "dormant";
    }
    return item.scope === filter;
  }
  if (section === "plugins" || section === "hooks") {
    if (filter === "enabled" || filter === "disabled") {
      return item.status === filter;
    }
    return item.scope === filter;
  }
  if (section === "mcp") {
    if (filter === "unassigned") {
      return item.scope === "unassigned";
    }
    return scopeHas(item, filter);
  }
  return true;
}

function itemMatchesQuery(item) {
  const query = els.searchInput.value.trim().toLowerCase();
  if (!query) {
    return true;
  }
  const detailsText = Object.values(item.details || {})
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .filter((value) => value !== null && value !== undefined)
    .join(" ");
  return `${item.search_text} ${detailsText}`.toLowerCase().includes(query);
}

function repoMatchesQuery(repo) {
  const query = els.searchInput.value.trim().toLowerCase();
  if (!query) {
    return true;
  }
  const caps = repoCapabilitySummary(repo);
  const capabilityNames = [
    ...caps.globalSkills,
    ...caps.repoSkills,
    ...caps.globalPlugins,
    ...caps.repoPlugins,
    ...caps.globalMcp,
    ...caps.directMcp,
    ...caps.globalHooks,
    ...caps.repoHooks,
  ]
    .map((item) => item.name)
    .join(" ");
  return `${repo.search_text} ${capabilityNames}`.toLowerCase().includes(query);
}

function repoCapabilitySummary(repo) {
  const globalSkillsForRepo = globalSkills();
  const repoSkills = repoScopedSkillsForRepo(repo);
  const globalPluginsForRepo = enabledGlobalPlugins();
  const repoPlugins = repoScopedPluginsForRepo(repo);
  const globalHooksForRepo = enabledGlobalHooks();
  const repoHooks = repoScopedHooksForRepo(repo);
  const globalMcpForRepo = globalMcp();
  const directMcp = repoDirectMcpForRepo(repo);
  return {
    globalSkills: globalSkillsForRepo,
    repoSkills,
    globalPlugins: globalPluginsForRepo,
    repoPlugins,
    globalHooks: globalHooksForRepo,
    repoHooks,
    globalMcp: globalMcpForRepo,
    directMcp,
    baseTotal: globalSkillsForRepo.length + globalPluginsForRepo.length + globalHooksForRepo.length + globalMcpForRepo.length,
    localTotal: repoSkills.length + repoPlugins.length + repoHooks.length,
  };
}

function repoScopedSkillsForRepo(repo) {
  return state.data.groups.skills.filter((item) => item.scope !== "global" && itemAppliesToRepo(item, repo));
}

function repoScopedPluginsForRepo(repo) {
  return state.data.groups.plugins.filter((item) => item.scope !== "global" && item.status !== "disabled" && itemAppliesToRepo(item, repo));
}

function repoScopedHooksForRepo(repo) {
  return state.data.groups.hooks.filter((item) => item.scope !== "global" && item.status === "enabled" && itemAppliesToRepo(item, repo));
}

function repoDirectMcpForRepo(repo) {
  const pluginNames = repoPluginNames(repo);
  return state.data.groups.mcp.filter((item) => {
    if (scopeHas(item, "global")) {
      return false;
    }
    if (cleanArray(item.repos).some((repoName) => sameRepo(repoName, repo.name))) {
      return true;
    }
    return cleanArray(item.details.plugins).some((plugin) => pluginNames.has(plugin));
  });
}

function repoPluginNames(repo) {
  return new Set(
    state.data.groups.plugins
      .filter((item) => item.status !== "disabled" && itemAppliesToRepo(item, repo))
      .map((item) => item.name),
  );
}

function repoHasCustomConfig(repo) {
  return Boolean(
    cleanArray(repo.details.mcp_presets).length ||
      repoScopedSkillsForRepo(repo).length ||
      repoScopedPluginsForRepo(repo).length ||
      repoScopedHooksForRepo(repo).length ||
      Object.keys(repo.details.features || {}).length,
  );
}

function globalSkills() {
  return state.data.groups.skills.filter((item) => item.scope === "global" && item.status !== "dormant");
}

function enabledGlobalPlugins() {
  return state.data.groups.plugins.filter((item) => item.scope === "global" && item.status === "enabled");
}

function enabledGlobalHooks() {
  return state.data.groups.hooks.filter((item) => item.scope === "global" && item.status === "enabled");
}

function globalMcp() {
  return state.data.groups.mcp.filter((item) => scopeHas(item, "global"));
}

function itemAppliesToRepo(item, repo) {
  if (item.scope === "global" || item.details.global === true) {
    return true;
  }
  return cleanArray(item.repos).some((repoName) => sameRepo(repoName, repo.name || repo));
}

function sameRepo(left, right) {
  return repoKey(left) === repoKey(right);
}

function repoKey(value) {
  const cleaned = String(value || "").replace(/\/$/, "");
  const withoutHome = cleaned.startsWith("~/") ? cleaned.slice(2) : cleaned;
  if (withoutHome.includes("/")) {
    const parts = withoutHome.split("/");
    return parts[parts.length - 1].toLowerCase();
  }
  return withoutHome.toLowerCase();
}

function repoDisplayName(value) {
  const key = repoKey(value);
  return key || String(value);
}

function scopeHas(item, scope) {
  return String(item.scope || "")
    .split("+")
    .includes(scope);
}

function labelForScope(item) {
  if (item.scope === "repo") {
    return "repo scoped";
  }
  if (item.scope === "repo-local") {
    return "repo local";
  }
  return item.scope;
}

function countItems(items, predicate) {
  return items.filter(predicate).length;
}

function cleanArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function compact(values) {
  return values.filter((value) => value !== null && value !== undefined && value !== "");
}

function titleCase(value) {
  if (!value) {
    return "";
  }
  return String(value).charAt(0).toUpperCase() + String(value).slice(1);
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString([], {
    month: "numeric",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function emptyState(message) {
  const empty = createElement("div", "empty-state");
  empty.append(createElement("p", "", message));
  return empty;
}

function renderLoadError(error) {
  els.metricsGrid.replaceChildren();
  els.filterBar.replaceChildren();
  els.warningPanel.classList.add("hidden");
  els.lastUpdated.textContent = "Not loaded";
  els.refreshStatus.textContent = "Auto-refresh failed";
  els.contentRegion.replaceChildren(emptyState(error.message));
}

function createElement(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== "") {
    node.textContent = text;
  }
  return node;
}

document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.section = button.dataset.section;
    state.filter = "all";
    render();
  });
});

function applySidebarState() {
  document.body.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);
  els.sidebarToggle.setAttribute("aria-expanded", String(!state.sidebarCollapsed));
  els.sidebarToggle.setAttribute(
    "aria-label",
    state.sidebarCollapsed ? "Expand navigation" : "Collapse navigation",
  );
  els.sidebarToggle.title = state.sidebarCollapsed ? "Expand navigation" : "Collapse navigation";
  els.sidebarToggle.querySelector("span").textContent = state.sidebarCollapsed ? ">" : "<";
}

els.sidebarToggle.addEventListener("click", () => {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  localStorage.setItem("agentControlSidebarCollapsed", String(state.sidebarCollapsed));
  applySidebarState();
});

els.searchInput.addEventListener("input", render);

applySidebarState();
loadData();
setInterval(() => loadData({ background: true }), AUTO_REFRESH_MS);
