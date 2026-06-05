import { useState } from 'react';
import { useNavigateRepo } from '../primitives';
import { cleanArray, repoDisplayName, sourceHref, sourceLabel } from '../selectors';
import type { ControlPlaneData, Item } from '../types';

type CatalogKind = 'skills' | 'plugins' | 'mcp' | 'hooks';

const KIND_LABEL: Record<CatalogKind, string> = {
  skills: 'Skills',
  plugins: 'Plugins',
  mcp: 'MCP presets',
  hooks: 'Hooks',
};

function isGlobal(item: Item): boolean {
  return item.scope === 'global' || item.details.global === true || item.scope.split('+').includes('global');
}

function usage(item: Item, totalRepos: number): number {
  return isGlobal(item) ? totalRepos : cleanArray(item.repos).length;
}

function subtitle(item: Item): string {
  const d = item.details;
  if (item.kind === 'skill') return String(d.source_path || '');
  if (item.kind === 'plugin') return [d.category, d.marketplace].filter(Boolean).join(' · ');
  if (item.kind === 'mcp') return [d.transport, d.url].filter(Boolean).join(' · ');
  if (item.kind === 'hook') {
    return [d.event, cleanArray(d.runtimes).join('/'), d.timeout ? `${d.timeout}s` : '']
      .filter(Boolean)
      .join(' · ');
  }
  return '';
}

function UsedBy({ item }: { item: Item }) {
  const navigate = useNavigateRepo();
  if (isGlobal(item)) {
    return (
      <span className="cat-all">
        <span className="cat-all-dot" aria-hidden="true" />
        Global
      </span>
    );
  }
  const repos = cleanArray(item.repos);
  const plugins = cleanArray(item.details.plugins);
  if (repos.length === 0 && plugins.length === 0) return <span className="cat-none">—</span>;
  return (
    <div className="cat-used-chips">
      {repos.map((r, i) => (
        <button key={`r-${i}`} type="button" className="cat-repo" onClick={() => navigate(r)}>
          {repoDisplayName(r)}
        </button>
      ))}
      {plugins.map((p, i) => (
        <span key={`p-${i}`} className="cat-plugin">
          {p}
        </span>
      ))}
    </div>
  );
}

// Plugins are always global, so "used by" is constant — what matters is whether
// the plugin is on. Sage dot = active, rose = disabled (and named, so it reads).
function PluginStatus({ item }: { item: Item }) {
  const disabled = item.status === 'disabled';
  return (
    <span className={`cat-state${disabled ? ' disabled' : ''}`}>
      <span className="cat-state-dot" aria-hidden="true" />
      {disabled ? 'Disabled' : 'Active'}
    </span>
  );
}

export function CatalogExplorer({
  data,
  kind,
  query,
}: {
  data: ControlPlaneData;
  kind: CatalogKind;
  query: string;
}) {
  const totalRepos = data.counts.repos;
  const isPlugins = kind === 'plugins';
  const [filter, setFilter] = useState<string>('all');
  const q = query.trim().toLowerCase();

  const base = data.groups[kind].filter((i) => !q || i.search_text.includes(q));

  // Plugins can only be global, so scope filtering is noise — filter by on/off
  // state instead. Every other kind keeps the global vs repo-scoped split.
  const filters: Array<{ id: string; label: string }> = isPlugins
    ? [
        { id: 'all', label: 'All' },
        { id: 'enabled', label: 'Enabled' },
        { id: 'disabled', label: 'Disabled' },
      ]
    : [
        { id: 'all', label: 'All' },
        { id: 'global', label: 'Global' },
        { id: 'repo', label: 'Repo-scoped' },
      ];

  const passes = (i: Item, f: string): boolean =>
    f === 'all' ? true : isPlugins ? i.status === f : f === 'global' ? isGlobal(i) : !isGlobal(i);

  // Map each filter to its scope colour so the chip row reads as a legend:
  // gold = global, sage = repo / enabled, rose = disabled.
  const chipTone = (id: string): string =>
    id === 'global'
      ? ' s-global'
      : id === 'repo'
        ? ' s-local'
        : id === 'enabled'
          ? ' s-enabled'
          : id === 'disabled'
            ? ' s-disabled'
            : '';

  const counts: Record<string, number> = {};
  for (const f of filters) counts[f.id] = base.filter((i) => passes(i, f.id)).length;

  const items = base
    .filter((i) => passes(i, filter))
    .slice()
    .sort((a, b) =>
      isPlugins
        ? Number(a.status === 'disabled') - Number(b.status === 'disabled') ||
          a.name.localeCompare(b.name)
        : usage(b, totalRepos) - usage(a, totalRepos) || a.name.localeCompare(b.name),
    );

  return (
    <div className="cat">
      <div className="cat-head">
        <h2>{KIND_LABEL[kind]}</h2>
        <div className="cat-filters">
          {filters.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`cat-chip${filter === f.id ? ' active' : ''}${chipTone(f.id)}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
              <strong>{counts[f.id]}</strong>
            </button>
          ))}
        </div>
        <span className="cat-hint">
          {isPlugins ? 'global base kit — on by default' : 'sorted by how many repos use it'}
        </span>
      </div>

      <table className="cat-table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">{isPlugins ? 'Status' : 'Used by'}</th>
            <th className="cat-src-h" scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className={isPlugins && item.status === 'disabled' ? 'is-disabled' : undefined}>
              <td className="cat-name">
                <span className="cat-name-main">{item.name}</span>
                {subtitle(item) ? (
                  <span className={`cat-sub${item.kind === 'skill' ? ' is-path' : ''}`}>{subtitle(item)}</span>
                ) : null}
              </td>
              <td className="cat-used">
                {isPlugins ? <PluginStatus item={item} /> : <UsedBy item={item} />}
              </td>
              <td className="cat-src">
                <a href={sourceHref(item)} target="_blank" rel="noreferrer">
                  {sourceLabel(item)}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 ? <p className="cat-empty">No {KIND_LABEL[kind].toLowerCase()} match this view.</p> : null}
    </div>
  );
}
