// Pure data derivations ported from the original vanilla dashboard.
// The Python engine owns the data; these only re-shape it for display.
import type {
  AttentionType,
  ControlPlaneData,
  FilterOption,
  Item,
  Metric,
  SectionId,
  Tone,
} from './types';

// ---- Primitives ----------------------------------------------------------
export function cleanArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter(Boolean).map(String) : [];
}

export function compact(values: Array<string | undefined | null>): string[] {
  return values.filter((v): v is string => v != null && v !== '');
}

export function titleCase(value: string | undefined): string {
  if (!value) return '';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function scopeHas(item: Item, scope: string): boolean {
  return String(item.scope || '').split('+').includes(scope);
}

export function labelForScope(item: Item): string {
  if (item.scope === 'repo') return 'repo scoped';
  if (item.scope === 'repo-local') return 'repo local';
  return item.scope;
}

export function repoKey(value: string): string {
  let v = String(value || '').trim();
  v = v.replace(/\/+$/, '');
  v = v.replace(/^~\//, '');
  if (v.includes('/')) v = v.slice(v.lastIndexOf('/') + 1);
  return v.toLowerCase();
}

export function repoDisplayName(value: string): string {
  return repoKey(value) || String(value);
}

export function sameRepo(a: string, b: string): boolean {
  return repoKey(a) === repoKey(b);
}

export function rootName(repoRoot: string): string {
  const parts = String(repoRoot || '').split('/').filter(Boolean);
  return parts.length ? parts[parts.length - 1] : repoRoot;
}

export function formatDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function countItems<T>(items: T[], predicate: (item: T) => boolean): number {
  return items.filter(predicate).length;
}

// ---- Global base getters -------------------------------------------------
export function globalSkills(d: ControlPlaneData): Item[] {
  return d.groups.skills.filter((i) => i.scope === 'global' && i.status !== 'dormant');
}
export function enabledGlobalPlugins(d: ControlPlaneData): Item[] {
  return d.groups.plugins.filter((i) => i.scope === 'global' && i.status === 'enabled');
}
export function enabledGlobalHooks(d: ControlPlaneData): Item[] {
  return d.groups.hooks.filter((i) => i.scope === 'global' && i.status === 'enabled');
}
export function globalMcp(d: ControlPlaneData): Item[] {
  return d.groups.mcp.filter((i) => scopeHas(i, 'global'));
}

// ---- Per-repo capability resolvers --------------------------------------
export function itemAppliesToRepo(item: Item, repo: Item): boolean {
  if (item.scope === 'global' || item.details.global === true) return true;
  return cleanArray(item.repos).some((r) => sameRepo(r, repo.name));
}

export function repoScopedSkillsForRepo(d: ControlPlaneData, repo: Item): Item[] {
  return d.groups.skills.filter((i) => i.scope !== 'global' && itemAppliesToRepo(i, repo));
}
export function repoScopedPluginsForRepo(d: ControlPlaneData, repo: Item): Item[] {
  return d.groups.plugins.filter(
    (i) => i.scope !== 'global' && i.status !== 'disabled' && itemAppliesToRepo(i, repo),
  );
}
export function repoScopedHooksForRepo(d: ControlPlaneData, repo: Item): Item[] {
  return d.groups.hooks.filter(
    (i) => i.scope !== 'global' && i.status === 'enabled' && itemAppliesToRepo(i, repo),
  );
}

function repoPluginNames(d: ControlPlaneData, repo: Item): Set<string> {
  const names = new Set<string>();
  for (const p of d.groups.plugins) {
    if (p.status !== 'disabled' && itemAppliesToRepo(p, repo)) names.add(p.name);
  }
  return names;
}

export function repoDirectMcpForRepo(d: ControlPlaneData, repo: Item): Item[] {
  const pluginNames = repoPluginNames(d, repo);
  return d.groups.mcp.filter((i) => {
    if (scopeHas(i, 'global')) return false;
    const byRepo = cleanArray(i.repos).some((r) => sameRepo(r, repo.name));
    const byPlugin = cleanArray(i.details.plugins).some((p) => pluginNames.has(p));
    return byRepo || byPlugin;
  });
}

export function repoHasCustomConfig(d: ControlPlaneData, repo: Item): boolean {
  return Boolean(
    cleanArray(repo.details.mcp_presets).length ||
      repoScopedSkillsForRepo(d, repo).length ||
      repoScopedPluginsForRepo(d, repo).length ||
      repoScopedHooksForRepo(d, repo).length ||
      Object.keys(repo.details.features || {}).length,
  );
}

export interface CapabilitySummary {
  globalSkills: Item[];
  repoSkills: Item[];
  globalPlugins: Item[];
  repoPlugins: Item[];
  globalHooks: Item[];
  repoHooks: Item[];
  globalMcp: Item[];
  directMcp: Item[];
  baseTotal: number;
  localTotal: number;
}

export function repoCapabilitySummary(d: ControlPlaneData, repo: Item): CapabilitySummary {
  const gSkills = globalSkills(d);
  const gPlugins = enabledGlobalPlugins(d);
  const gHooks = enabledGlobalHooks(d);
  const gMcp = globalMcp(d);
  const repoSkills = repoScopedSkillsForRepo(d, repo);
  const repoPlugins = repoScopedPluginsForRepo(d, repo);
  const repoHooks = repoScopedHooksForRepo(d, repo);
  const directMcp = repoDirectMcpForRepo(d, repo);
  return {
    globalSkills: gSkills,
    repoSkills,
    globalPlugins: gPlugins,
    repoPlugins,
    globalHooks: gHooks,
    repoHooks,
    globalMcp: gMcp,
    directMcp,
    baseTotal: gSkills.length + gPlugins.length + gHooks.length + gMcp.length,
    localTotal: repoSkills.length + repoPlugins.length + repoHooks.length,
  };
}

// ---- Attention -----------------------------------------------------------
export function unassignedMcp(d: ControlPlaneData): Item[] {
  return d.groups.mcp.filter((i) => i.scope === 'unassigned');
}
export function disabledItems(d: ControlPlaneData): Item[] {
  return [...d.groups.plugins, ...d.groups.hooks].filter((i) => i.status === 'disabled');
}
export function dormantSkills(d: ControlPlaneData): Item[] {
  return d.groups.skills.filter((i) => i.status === 'dormant' || i.scope === 'dormant');
}
export function missingRepoAssignments(d: ControlPlaneData): Item[] {
  return [...d.groups.skills, ...d.groups.plugins, ...d.groups.hooks].filter(
    (i) => i.scope === 'repo' && cleanArray(i.repos).length === 0,
  );
}

function tag(items: Item[], attentionType: AttentionType): Item[] {
  return items.map((item) => ({ ...item, attentionType }));
}

export function attentionItems(d: ControlPlaneData): Item[] {
  const warnings: Item[] = d.warnings.map((w) => ({
    id: `warning:${w.code}:${w.message}`,
    kind: 'warning',
    name: w.code,
    title: w.message,
    scope: 'registry',
    status: w.severity || 'warning',
    source: w.source,
    repos: [],
    details: { code: w.code },
    search_text: `${w.code} ${w.message} ${w.source}`.toLowerCase(),
    attentionType: 'warnings',
  }));
  return [
    ...warnings,
    ...tag(unassignedMcp(d), 'unassigned'),
    ...tag(disabledItems(d), 'disabled'),
    ...tag(dormantSkills(d), 'dormant'),
    ...tag(missingRepoAssignments(d), 'unscoped'),
  ];
}

// ---- Scope tones ---------------------------------------------------------
export function scopeToneForItem(item: Item): Tone {
  if (item.scope === 'global' || item.details.global === true || scopeHas(item, 'global')) {
    return 'scope-global';
  }
  if (item.scope === 'repo' || item.scope === 'repo-local' || scopeHas(item, 'repo')) {
    return 'scope-local';
  }
  return '';
}

export function scopeToneForFilter(filter: string): Tone {
  if (filter === 'global') return 'scope-global';
  if (
    ['repo', 'repo-scoped', 'repo-local', 'repo-skills', 'repo-plugins', 'repo-mcp', 'custom'].includes(
      filter,
    )
  ) {
    return 'scope-local';
  }
  return '';
}

// ---- Metrics -------------------------------------------------------------
function metric(label: string, value: number, tone: Tone = ''): Metric {
  return { label, value, tone };
}

export function metricsForSection(d: ControlPlaneData, section: SectionId): Metric[] {
  const { groups, counts } = d;
  const warnTone = (n: number): Tone => (n ? 'warning' : '');
  switch (section) {
    case 'attention': {
      const m = (label: string, value: number) => metric(label, value, warnTone(value));
      return [
        m('Warnings', d.warnings.length),
        m('Unassigned MCP', unassignedMcp(d).length),
        m('Disabled', disabledItems(d).length),
        m('Dormant', dormantSkills(d).length),
        m('Missing repos', missingRepoAssignments(d).length),
      ];
    }
    case 'skills':
      return [
        metric('Global', countItems(groups.skills, (i) => i.scope === 'global'), 'scope-global'),
        metric('Repo scoped', countItems(groups.skills, (i) => i.scope === 'repo'), 'scope-local'),
        metric('Repo local', countItems(groups.skills, (i) => i.scope === 'repo-local'), 'scope-local'),
        metric('Owned', countItems(groups.skills, (i) => i.details.origin === 'owned')),
        metric('External', countItems(groups.skills, (i) => i.details.origin === 'external')),
      ];
    case 'plugins':
      return [
        metric('Enabled', countItems(groups.plugins, (i) => i.status === 'enabled')),
        metric('Disabled', countItems(groups.plugins, (i) => i.status === 'disabled'), 'warning'),
        metric('Global', countItems(groups.plugins, (i) => i.scope === 'global'), 'scope-global'),
        metric('Repo scoped', countItems(groups.plugins, (i) => i.scope === 'repo'), 'scope-local'),
        metric('Repo local', countItems(groups.plugins, (i) => i.scope === 'repo-local'), 'scope-local'),
      ];
    case 'mcp':
      return [
        metric('Global', countItems(groups.mcp, (i) => scopeHas(i, 'global')), 'scope-global'),
        metric('Repo', countItems(groups.mcp, (i) => scopeHas(i, 'repo')), 'scope-local'),
        metric('Plugin', countItems(groups.mcp, (i) => scopeHas(i, 'plugin'))),
        metric('Unassigned', countItems(groups.mcp, (i) => i.scope === 'unassigned'), 'warning'),
      ];
    case 'repos':
      return [
        metric('Managed', groups.repos.length),
        metric('Repo skills', countItems(groups.repos, (r) => repoScopedSkillsForRepo(d, r).length > 0)),
        metric('Repo plugins', countItems(groups.repos, (r) => repoScopedPluginsForRepo(d, r).length > 0)),
        metric('Repo MCP', countItems(groups.repos, (r) => repoDirectMcpForRepo(d, r).length > 0)),
        metric('Warnings', counts.warnings, warnTone(counts.warnings)),
      ];
    case 'hooks':
      return [
        metric('Enabled', countItems(groups.hooks, (i) => i.status === 'enabled')),
        metric('Disabled', countItems(groups.hooks, (i) => i.status === 'disabled'), 'warning'),
        metric('Global', countItems(groups.hooks, (i) => i.scope === 'global'), 'scope-global'),
        metric('Repo scoped', countItems(groups.hooks, (i) => i.scope === 'repo'), 'scope-local'),
      ];
    default: {
      const globalBase =
        globalSkills(d).length +
        enabledGlobalPlugins(d).length +
        enabledGlobalHooks(d).length +
        globalMcp(d).length;
      return [
        metric('Control items', counts.items),
        metric('Managed repos', counts.repos),
        metric('Global base', globalBase, 'scope-global'),
        metric('Repo additions', counts.repo_scoped, 'scope-local'),
        metric('Warnings', counts.warnings, warnTone(counts.warnings)),
      ];
    }
  }
}

// ---- Filters -------------------------------------------------------------
export const filterOptions: Record<SectionId, FilterOption[]> = {
  overview: [{ id: 'all', label: 'All' }],
  attention: [
    { id: 'all', label: 'All' },
    { id: 'warnings', label: 'Warnings' },
    { id: 'unassigned', label: 'Unassigned' },
    { id: 'disabled', label: 'Disabled' },
    { id: 'dormant', label: 'Dormant' },
    { id: 'unscoped', label: 'Missing repos' },
  ],
  repos: [
    { id: 'all', label: 'All' },
    { id: 'repo-skills', label: 'Repo skills' },
    { id: 'repo-plugins', label: 'Repo plugins' },
    { id: 'repo-mcp', label: 'Repo MCP' },
    { id: 'custom', label: 'Custom config' },
  ],
  skills: [
    { id: 'all', label: 'All' },
    { id: 'global', label: 'Global' },
    { id: 'repo', label: 'Repo scoped' },
    { id: 'repo-local', label: 'Repo local' },
    { id: 'owned', label: 'Owned' },
    { id: 'external', label: 'External' },
    { id: 'dormant', label: 'Dormant' },
  ],
  plugins: [
    { id: 'all', label: 'All' },
    { id: 'enabled', label: 'Enabled' },
    { id: 'disabled', label: 'Disabled' },
    { id: 'global', label: 'Global' },
    { id: 'repo', label: 'Repo scoped' },
    { id: 'repo-local', label: 'Repo local' },
  ],
  mcp: [
    { id: 'all', label: 'All' },
    { id: 'global', label: 'Global' },
    { id: 'repo', label: 'Repo' },
    { id: 'plugin', label: 'Plugin' },
    { id: 'unassigned', label: 'Unassigned' },
  ],
  hooks: [
    { id: 'all', label: 'All' },
    { id: 'enabled', label: 'Enabled' },
    { id: 'disabled', label: 'Disabled' },
    { id: 'global', label: 'Global' },
    { id: 'repo', label: 'Repo scoped' },
  ],
};

export function itemPassesFilter(item: Item, section: SectionId, filter: string): boolean {
  if (filter === 'all') return true;
  if (section === 'skills') {
    if (filter === 'owned' || filter === 'external') return item.details.origin === filter;
    if (filter === 'dormant') return item.status === 'dormant' || item.scope === 'dormant';
    return item.scope === filter;
  }
  if (section === 'plugins' || section === 'hooks') {
    if (filter === 'enabled' || filter === 'disabled') return item.status === filter;
    return item.scope === filter;
  }
  if (section === 'mcp') {
    if (filter === 'unassigned') return item.scope === 'unassigned';
    return scopeHas(item, filter);
  }
  return true;
}

// ---- Search --------------------------------------------------------------
function normalize(query: string): string {
  return query.trim().toLowerCase();
}

export function itemMatchesQuery(item: Item, query: string): boolean {
  const q = normalize(query);
  if (!q) return true;
  const detailsText = Object.values(item.details || {})
    .flatMap((v) => (Array.isArray(v) ? v : [v]))
    .filter((v) => v != null)
    .join(' ');
  return `${item.search_text} ${detailsText}`.toLowerCase().includes(q);
}

export function repoMatchesQuery(d: ControlPlaneData, repo: Item, query: string): boolean {
  const q = normalize(query);
  if (!q) return true;
  const caps = repoCapabilitySummary(d, repo);
  const names = [
    ...caps.globalSkills,
    ...caps.repoSkills,
    ...caps.globalPlugins,
    ...caps.repoPlugins,
    ...caps.globalMcp,
    ...caps.directMcp,
    ...caps.globalHooks,
    ...caps.repoHooks,
  ].map((i) => i.name);
  return `${repo.search_text} ${names.join(' ')}`.toLowerCase().includes(q);
}

export function attentionItemMatchesQuery(item: Item, query: string): boolean {
  const q = normalize(query);
  if (!q) return true;
  if (item.kind === 'warning') return item.search_text.includes(q);
  return itemMatchesQuery(item, query);
}

// ---- Filtered collections ------------------------------------------------
export function filterRepos(
  d: ControlPlaneData,
  repos: Item[],
  filter: string,
  query: string,
  includeQuery: boolean,
): Item[] {
  return repos.filter((repo) => {
    if (filter === 'repo-skills' && repoScopedSkillsForRepo(d, repo).length === 0) return false;
    if (filter === 'repo-plugins' && repoScopedPluginsForRepo(d, repo).length === 0) return false;
    if (filter === 'repo-mcp' && repoDirectMcpForRepo(d, repo).length === 0) return false;
    if (filter === 'custom' && !repoHasCustomConfig(d, repo)) return false;
    if (includeQuery && !repoMatchesQuery(d, repo, query)) return false;
    return true;
  });
}

export function filterAttentionItems(
  d: ControlPlaneData,
  filter: string,
  query: string,
  includeQuery: boolean,
): Item[] {
  let items = attentionItems(d).filter((i) => filter === 'all' || i.attentionType === filter);
  if (includeQuery) items = items.filter((i) => attentionItemMatchesQuery(i, query));
  return items;
}

export function filteredItems(
  d: ControlPlaneData,
  section: SectionId,
  filter: string,
  query: string,
): Item[] {
  const items = (d.groups as unknown as Record<string, Item[]>)[section] || [];
  return items.filter((i) => itemPassesFilter(i, section, filter) && itemMatchesQuery(i, query));
}

export function filteredRepos(d: ControlPlaneData, filter: string, query: string): Item[] {
  return filterRepos(d, d.groups.repos, filter, query, true);
}

export function countForFilter(
  d: ControlPlaneData,
  section: SectionId,
  filter: string,
): number {
  if (section === 'attention') return filterAttentionItems(d, filter, '', false).length;
  if (section === 'repos') return filterRepos(d, d.groups.repos, filter, '', false).length;
  const items = (d.groups as unknown as Record<string, Item[]>)[section] || [];
  if (filter === 'all') return items.length;
  return countItems(items, (i) => itemPassesFilter(i, section, filter));
}

// ---- Section meta + sources ---------------------------------------------
export const sectionMeta: Record<SectionId, { eyebrow: string; title: string }> = {
  overview: { eyebrow: 'Overview', title: 'Control-plane status' },
  attention: { eyebrow: 'Attention', title: 'Needs attention' },
  repos: { eyebrow: 'Repos', title: 'Managed repo map' },
  skills: { eyebrow: 'Skills', title: 'Skill availability' },
  plugins: { eyebrow: 'Plugins', title: 'Codex plugin state' },
  mcp: { eyebrow: 'MCP', title: 'MCP presets' },
  hooks: { eyebrow: 'Hooks', title: 'Lifecycle hooks' },
};

export function navCount(d: ControlPlaneData, section: SectionId): number {
  switch (section) {
    case 'overview':
      return d.counts.items;
    case 'attention':
      return attentionItems(d).length;
    case 'repos':
      return d.counts.repos;
    case 'skills':
      return d.counts.skills;
    case 'plugins':
      return d.counts.plugins;
    case 'mcp':
      return d.counts.mcp;
    case 'hooks':
      return d.counts.hooks;
  }
}

export const sourceOrder = ['skills', 'plugins', 'mcp', 'hooks', 'repos'] as const;
export const sourceLabels: Record<string, string> = {
  skills: 'Skills registry',
  plugins: 'Plugin registry',
  mcp: 'MCP presets',
  hooks: 'Hook registry',
  repos: 'Repo bootstrap',
};

export function sourceLabel(item: Item): string {
  return item.kind === 'skill' && item.details.source_path ? 'SKILL.md' : 'Registry';
}

export function sourceHref(item: Item): string {
  if (item.kind === 'skill' && item.details.source_path) {
    return `/source/${item.details.source_path}/SKILL.md`;
  }
  return `/source/${item.source}`;
}
