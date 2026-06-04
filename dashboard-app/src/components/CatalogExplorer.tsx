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

type ScopeFilter = 'all' | 'global' | 'repo';

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

function UsedBy({ item, totalRepos }: { item: Item; totalRepos: number }) {
  const navigate = useNavigateRepo();
  if (isGlobal(item)) return <span className="cat-all">All {totalRepos}</span>;
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
  const [scope, setScope] = useState<ScopeFilter>('all');
  const q = query.trim().toLowerCase();

  const base = data.groups[kind].filter((i) => !q || i.search_text.includes(q));
  const counts: Record<ScopeFilter, number> = {
    all: base.length,
    global: base.filter(isGlobal).length,
    repo: base.filter((i) => !isGlobal(i)).length,
  };
  const items = base
    .filter((i) => scope === 'all' || (scope === 'global' ? isGlobal(i) : !isGlobal(i)))
    .slice()
    .sort((a, b) => usage(b, totalRepos) - usage(a, totalRepos) || a.name.localeCompare(b.name));

  const filters: Array<{ id: ScopeFilter; label: string }> = [
    { id: 'all', label: 'All' },
    { id: 'global', label: 'Global' },
    { id: 'repo', label: 'Repo-scoped' },
  ];

  return (
    <div className="cat">
      <div className="cat-head">
        <h2>{KIND_LABEL[kind]}</h2>
        <div className="cat-filters">
          {filters.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`cat-chip${scope === f.id ? ' active' : ''}`}
              onClick={() => setScope(f.id)}
            >
              {f.label}
              <strong>{counts[f.id]}</strong>
            </button>
          ))}
        </div>
        <span className="cat-hint">sorted by how many repos use it</span>
      </div>

      <table className="cat-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Used by</th>
            <th className="cat-src-h">Source</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="cat-name">
                <span className="cat-name-main">{item.name}</span>
                {subtitle(item) ? <span className="cat-sub">{subtitle(item)}</span> : null}
              </td>
              <td className="cat-used">
                <UsedBy item={item} totalRepos={totalRepos} />
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
