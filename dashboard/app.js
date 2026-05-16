const state = {
  data: null,
  selectedKind: "all",
  selectedId: null,
};

const els = {
  repoRoot: document.querySelector("#repoRoot"),
  sourceLinks: document.querySelector("#sourceLinks"),
  searchInput: document.querySelector("#searchInput"),
  scopeFilter: document.querySelector("#scopeFilter"),
  statusFilter: document.querySelector("#statusFilter"),
  refreshButton: document.querySelector("#refreshButton"),
  itemTable: document.querySelector("#itemTable"),
  tableTitle: document.querySelector("#tableTitle"),
  resultMeta: document.querySelector("#resultMeta"),
  lastUpdated: document.querySelector("#lastUpdated"),
  warningPanel: document.querySelector("#warningPanel"),
  warningList: document.querySelector("#warningList"),
  warningCount: document.querySelector("#warningCount"),
  detailKind: document.querySelector("#detailKind"),
  detailTitle: document.querySelector("#detailTitle"),
  detailFacts: document.querySelector("#detailFacts"),
  detailJson: document.querySelector("#detailJson"),
  detailSourceLink: document.querySelector("#detailSourceLink"),
  metricItems: document.querySelector("#metricItems"),
  metricGlobal: document.querySelector("#metricGlobal"),
  metricRepoScoped: document.querySelector("#metricRepoScoped"),
  metricWarnings: document.querySelector("#metricWarnings"),
  navCountAll: document.querySelector("#navCountAll"),
  navCountSkills: document.querySelector("#navCountSkills"),
  navCountPlugins: document.querySelector("#navCountPlugins"),
  navCountMcp: document.querySelector("#navCountMcp"),
  navCountRepos: document.querySelector("#navCountRepos"),
  navCountHooks: document.querySelector("#navCountHooks"),
};

const labels = {
  all: "All Items",
  skill: "Skills",
  plugin: "Plugins",
  mcp: "MCP Presets",
  repo: "Repos",
  hook: "Hooks",
};

async function loadData() {
  els.refreshButton.disabled = true;
  els.refreshButton.textContent = "Loading";
  try {
    const response = await fetch("/api/control-plane", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Dashboard API returned ${response.status}`);
    }
    state.data = await response.json();
    if (!state.selectedId && state.data.items.length > 0) {
      state.selectedId = state.data.items[0].id;
    }
    render();
  } catch (error) {
    renderLoadError(error);
  } finally {
    els.refreshButton.disabled = false;
    els.refreshButton.textContent = "Refresh";
  }
}

function render() {
  const data = state.data;
  if (!data) {
    return;
  }
  const counts = data.counts;
  els.repoRoot.textContent = data.repo_root;
  els.metricItems.textContent = counts.items;
  els.metricGlobal.textContent = counts.global;
  els.metricRepoScoped.textContent = counts.repo_scoped;
  els.metricWarnings.textContent = counts.warnings;
  els.navCountAll.textContent = counts.items;
  els.navCountSkills.textContent = counts.skills;
  els.navCountPlugins.textContent = counts.plugins;
  els.navCountMcp.textContent = counts.mcp;
  els.navCountRepos.textContent = counts.repos;
  els.navCountHooks.textContent = counts.hooks;
  els.lastUpdated.textContent = `Updated ${formatDate(data.generated_at_utc)}`;

  renderSources(data.sources);
  renderWarnings(data.warnings);
  renderTable(filteredItems());
  renderDetail(findSelectedItem());
}

function renderSources(sources) {
  els.sourceLinks.replaceChildren();
  Object.entries(sources).forEach(([name, source]) => {
    const link = document.createElement("a");
    link.className = "source-link";
    link.href = `/source/${source.path}`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = `${name}: ${source.path}`;
    els.sourceLinks.append(link);
  });
}

function renderWarnings(warnings) {
  els.warningList.replaceChildren();
  els.warningCount.textContent = warnings.length;
  els.warningPanel.classList.toggle("hidden", warnings.length === 0);
  warnings.slice(0, 8).forEach((warning) => {
    const item = document.createElement("div");
    item.className = `warning-item ${warning.severity === "error" ? "error" : ""}`;

    const title = document.createElement("strong");
    title.textContent = warning.message;

    const meta = document.createElement("span");
    meta.textContent = `${warning.code} / ${warning.source}`;

    item.append(title, meta);
    els.warningList.append(item);
  });
}

function filteredItems() {
  const data = state.data;
  if (!data) {
    return [];
  }
  const query = els.searchInput.value.trim().toLowerCase();
  const scope = els.scopeFilter.value;
  const status = els.statusFilter.value;
  return data.items.filter((item) => {
    if (state.selectedKind !== "all" && item.kind !== state.selectedKind) {
      return false;
    }
    if (scope !== "all" && item.scope !== scope && !item.scope.includes(scope)) {
      return false;
    }
    if (status !== "all" && item.status !== status) {
      return false;
    }
    if (query && !item.search_text.includes(query)) {
      return false;
    }
    return true;
  });
}

function renderTable(items) {
  els.itemTable.replaceChildren();
  els.tableTitle.textContent = labels[state.selectedKind] || "Items";
  els.resultMeta.textContent = `${items.length} shown`;

  if (items.length === 0) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "No matching registry items";
    row.append(cell);
    els.itemTable.append(row);
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("tr");
    row.className = item.id === state.selectedId ? "selected" : "";
    row.tabIndex = 0;
    row.addEventListener("click", () => {
      state.selectedId = item.id;
      renderTable(filteredItems());
      renderDetail(item);
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        state.selectedId = item.id;
        renderTable(filteredItems());
        renderDetail(item);
      }
    });

    row.append(
      cellName(item),
      cellBadge(item.kind, item.kind, "Type"),
      cellBadge(item.scope, item.scope, "Scope"),
      cellBadge(item.status, item.status, "Status"),
      cellRepos(item.repos),
      cellSource(item.source),
    );
    els.itemTable.append(row);
  });
}

function cellName(item) {
  const cell = document.createElement("td");
  cell.className = "name-cell";
  cell.dataset.label = "Name";

  const name = document.createElement("strong");
  name.textContent = item.title;

  const sub = document.createElement("span");
  sub.textContent = subtitleFor(item);

  cell.append(name, sub);
  return cell;
}

function subtitleFor(item) {
  if (item.kind === "skill") {
    return compact([item.details.origin, item.details.source_path]).join(" / ");
  }
  if (item.kind === "plugin") {
    return compact([item.details.marketplace, item.details.category]).join(" / ");
  }
  if (item.kind === "mcp") {
    return compact([item.details.transport, item.details.url]).join(" / ");
  }
  if (item.kind === "repo") {
    return item.details.path || item.name;
  }
  if (item.kind === "hook") {
    return compact([item.details.event, `timeout ${item.details.timeout}s`]).join(" / ");
  }
  return item.source;
}

function cellBadge(text, tone, label) {
  const cell = document.createElement("td");
  cell.dataset.label = label;
  const badge = document.createElement("span");
  badge.className = `badge ${tone}`;
  badge.textContent = text;
  cell.append(badge);
  return cell;
}

function cellRepos(repos) {
  const cell = document.createElement("td");
  cell.dataset.label = "Repos";
  const wrap = document.createElement("div");
  wrap.className = "repo-list";
  if (!repos.length) {
    const span = document.createElement("span");
    span.className = "muted";
    span.textContent = "-";
    wrap.append(span);
  } else {
    repos.slice(0, 6).forEach((repo) => {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = repoName(repo);
      wrap.append(badge);
    });
    if (repos.length > 6) {
      const more = document.createElement("span");
      more.className = "badge";
      more.textContent = `+${repos.length - 6}`;
      wrap.append(more);
    }
  }
  cell.append(wrap);
  return cell;
}

function cellSource(source) {
  const cell = document.createElement("td");
  cell.className = "source-cell";
  cell.dataset.label = "Source";
  const link = document.createElement("a");
  link.href = `/source/${source}`;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = source;
  cell.append(link);
  return cell;
}

function renderDetail(item) {
  if (!item) {
    els.detailKind.textContent = "Detail";
    els.detailTitle.textContent = "Select an item";
    els.detailFacts.replaceChildren();
    els.detailJson.textContent = "";
    els.detailSourceLink.href = "#";
    return;
  }

  els.detailKind.textContent = item.kind;
  els.detailTitle.textContent = item.title;
  els.detailSourceLink.href = `/source/${item.source}`;
  els.detailFacts.replaceChildren();

  addFact("Name", item.name);
  addFact("Scope", item.scope);
  addFact("Status", item.status);
  addFact("Repos", item.repos.length ? item.repos.map(repoName).join(", ") : "-");
  addFact("Source", item.source);

  Object.entries(item.details).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "" || key === "command") {
      return;
    }
    addFact(formatKey(key), formatValue(value));
  });

  els.detailJson.textContent = JSON.stringify(item, null, 2);
}

function addFact(label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  els.detailFacts.append(dt, dd);
}

function findSelectedItem() {
  const items = filteredItems();
  return items.find((item) => item.id === state.selectedId) || items[0] || null;
}

function renderLoadError(error) {
  els.itemTable.replaceChildren();
  const row = document.createElement("tr");
  row.className = "empty-row";
  const cell = document.createElement("td");
  cell.colSpan = 6;
  cell.textContent = error.message;
  row.append(cell);
  els.itemTable.append(row);
}

function compact(values) {
  return values.filter((value) => value !== null && value !== undefined && value !== "");
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatKey(value) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "-";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function repoName(value) {
  const cleaned = String(value).replace(/\/$/, "");
  if (cleaned.startsWith("~/")) {
    const parts = cleaned.slice(2).split("/");
    return parts[parts.length - 1];
  }
  if (cleaned.includes("/")) {
    const parts = cleaned.split("/");
    return parts[parts.length - 1];
  }
  return cleaned;
}

document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.selectedKind = button.dataset.kind;
    state.selectedId = null;
    render();
  });
});

els.searchInput.addEventListener("input", render);
els.scopeFilter.addEventListener("change", render);
els.statusFilter.addEventListener("change", render);
els.refreshButton.addEventListener("click", loadData);

loadData();
