// Pure data derivations ported from the original vanilla dashboard.
// The Python engine owns the data; these only re-shape it for display.
import type { AttentionType, ControlPlaneData, Item, SectionId } from './types';

// ---- Primitives ----------------------------------------------------------
export function cleanArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter(Boolean).map(String) : [];
}

export function compact(values: Array<string | undefined | null>): string[] {
  return values.filter((v): v is string => v != null && v !== '');
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

// ---- Global base getters -------------------------------------------------
export function globalSkills(d: ControlPlaneData): Item[] {
  return d.groups.skills.filter((i) => i.scope === 'global' && i.status !== 'dormant');
}
export function enabledGlobalPlugins(d: ControlPlaneData): Item[] {
  return d.groups.plugins.filter((i) => i.scope === 'global' && i.status === 'enabled');
}
// Headline counts mean "what the agent actually has on" — active, not registered.
// Disabled plugins / hooks stay discoverable via the Attention view.
export function enabledPlugins(d: ControlPlaneData): Item[] {
  return d.groups.plugins.filter((i) => i.status === 'enabled');
}
export function enabledHooks(d: ControlPlaneData): Item[] {
  return d.groups.hooks.filter((i) => i.status === 'enabled');
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

export function filterAttentionItems(d: ControlPlaneData, filter: string): Item[] {
  return attentionItems(d).filter((i) => filter === 'all' || i.attentionType === filter);
}

// ---- Nav + sources -------------------------------------------------------
export function navCount(d: ControlPlaneData, section: SectionId): number {
  switch (section) {
    case 'overview':
      return 0;
    case 'board':
      return d.capabilities?.length ?? 0;
    case 'attention':
      return attentionItems(d).length;
    case 'repos':
      return d.counts.repos;
    case 'skills':
      return d.counts.skills;
    case 'plugins':
      return enabledPlugins(d).length;
    case 'mcp':
      return d.counts.mcp;
    case 'hooks':
      return enabledHooks(d).length;
    case 'codex':
      return d.global_config?.codex.length ?? 0;
    case 'claude':
      return d.global_config?.claude.length ?? 0;
  }
}

export function sourceLabel(item: Item): string {
  return item.kind === 'skill' && item.details.source_path ? 'SKILL.md' : 'Registry';
}

export function sourceHref(item: Item): string {
  if (item.kind === 'skill' && item.details.source_path) {
    return `/source/${item.details.source_path}/SKILL.md`;
  }
  return `/source/${item.source}`;
}
