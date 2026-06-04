import { useState } from 'react';
import { useNavigateRepo } from '../primitives';
import {
  cleanArray,
  labelForScope,
  repoDisplayName,
  sourceHref,
  sourceLabel,
  titleCase,
} from '../selectors';
import type { ControlPlaneData, Item } from '../types';

type CatalogKind = 'skills' | 'plugins' | 'mcp' | 'hooks';

const KIND_LABEL: Record<CatalogKind, string> = {
  skills: 'Skills',
  plugins: 'Plugins',
  mcp: 'MCP presets',
  hooks: 'Hooks',
};

function Pill({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <span className="re-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

function isGlobal(item: Item): boolean {
  return item.scope === 'global' || item.details.global === true || item.scope.split('+').includes('global');
}

function RepoUsage({ item }: { item: Item }) {
  const navigate = useNavigateRepo();
  if (isGlobal(item)) return <span className="re-chip accent">All repos</span>;
  const repos = cleanArray(item.repos);
  const plugins = cleanArray(item.details.plugins);
  if (repos.length === 0 && plugins.length === 0) return <span className="re-empty">No repo assignment</span>;
  return (
    <div className="re-chips">
      {repos.map((r, i) => (
        <button
          key={`r-${r}-${i}`}
          type="button"
          className="re-chip accent re-chip-btn"
          onClick={() => navigate(r)}
        >
          {repoDisplayName(r)}
        </button>
      ))}
      {plugins.map((p, i) => (
        <span key={`p-${p}-${i}`} className="re-chip">
          plugin: {p}
        </span>
      ))}
    </div>
  );
}

function Detail({ item }: { item: Item }) {
  const d = item.details;
  return (
    <div className="re-detail-inner">
      <header className="re-detail-head">
        <h2>{item.name}</h2>
        {d.source_path ? <code className="re-path">{d.source_path}</code> : null}
        <div className="re-pills">
          <Pill label="scope" value={labelForScope(item)} />
          <Pill label="status" value={item.status} />
          {item.kind === 'skill' ? <Pill label="origin" value={titleCase(d.origin)} /> : null}
          {item.kind === 'plugin' ? <Pill label="category" value={d.category} /> : null}
          {item.kind === 'plugin' ? <Pill label="marketplace" value={d.marketplace} /> : null}
          {item.kind === 'mcp' ? <Pill label="transport" value={d.transport} /> : null}
          {item.kind === 'hook' ? <Pill label="event" value={d.event} /> : null}
          {item.kind === 'hook' ? <Pill label="runtimes" value={cleanArray(d.runtimes).join(', ')} /> : null}
          {item.kind === 'hook' && d.timeout ? <Pill label="timeout" value={`${d.timeout}s`} /> : null}
        </div>
      </header>

      {item.kind === 'mcp' && d.url ? (
        <section className="re-cap">
          <div className="re-cap-head">
            <h4>Endpoint</h4>
          </div>
          <code className="re-path">{d.url}</code>
        </section>
      ) : null}

      {item.kind === 'skill' && d.upstream_ref && d.upstream_ref !== '-' ? (
        <section className="re-cap">
          <div className="re-cap-head">
            <h4>Upstream</h4>
          </div>
          <code className="re-path">{String(d.upstream_ref)}</code>
        </section>
      ) : null}

      <section className="re-cap">
        <div className="re-cap-head">
          <h4>Used by</h4>
        </div>
        <RepoUsage item={item} />
      </section>

      <section className="re-cap">
        <div className="re-cap-head">
          <h4>Source</h4>
        </div>
        <a className="re-source-link" href={sourceHref(item)} target="_blank" rel="noreferrer">
          {sourceLabel(item)} · {item.source}
        </a>
      </section>
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
  const q = query.trim().toLowerCase();
  const items = data.groups[kind]
    .filter((i) => !q || i.search_text.includes(q))
    .slice()
    .sort((a, b) => {
      const ag = isGlobal(a) ? 0 : 1;
      const bg = isGlobal(b) ? 0 : 1;
      return ag - bg || a.name.localeCompare(b.name);
    });
  const [selId, setSelId] = useState('');
  const selected = items.find((i) => i.id === selId) ?? items[0];

  return (
    <div className="repo-explorer">
      <aside className="re-list">
        <div className="re-list-head">
          <span>{KIND_LABEL[kind]}</span>
          <strong>{items.length}</strong>
        </div>
        <ul>
          {items.map((item) => {
            const isSel = selected && item.id === selected.id;
            const repos = cleanArray(item.repos).length;
            const meta = isGlobal(item) ? 'global' : repos ? `${repos} repo${repos > 1 ? 's' : ''}` : item.status;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={`re-list-item${isSel ? ' active' : ''}`}
                  onClick={() => setSelId(item.id)}
                >
                  <span className="re-list-name">{item.name}</span>
                  <span className="re-list-meta">{meta}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>
      <div className="re-detail">
        {selected ? (
          <Detail item={selected} />
        ) : (
          <div className="empty-state">
            <p>No {KIND_LABEL[kind].toLowerCase()} match this search.</p>
          </div>
        )}
      </div>
    </div>
  );
}
