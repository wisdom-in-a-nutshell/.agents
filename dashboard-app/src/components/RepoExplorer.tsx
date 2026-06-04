import { useState } from 'react';
import {
  cleanArray,
  filteredRepos,
  itemAppliesToRepo,
  repoCapabilitySummary,
  repoKey,
} from '../selectors';
import type { ControlPlaneData, Item } from '../types';

function Badge({ text }: { text: string }) {
  return <span className="re-badge">{text}</span>;
}

function Chips({ items, accent, empty }: { items: string[]; accent?: boolean; empty: string }) {
  if (items.length === 0) return <span className="re-empty">{empty}</span>;
  return (
    <div className="re-chips">
      {items.map((t, i) => (
        <span key={`${t}-${i}`} className={`re-chip${accent ? ' accent' : ''}`}>
          {t}
        </span>
      ))}
    </div>
  );
}

function CapGroup({
  title,
  runtime,
  count,
  children,
}: {
  title: string;
  runtime: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section className="re-cap">
      <div className="re-cap-head">
        <h4>{title}</h4>
        <Badge text={runtime} />
        {count != null ? <strong>{count}</strong> : null}
      </div>
      {children}
    </section>
  );
}

function ConfigPill({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <span className="re-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

function RepoDetail({ data, repo }: { data: ControlPlaneData; repo: Item }) {
  const caps = repoCapabilitySummary(data, repo);
  const d = repo.details;
  const devServers = data.groups.dev_servers.filter((s) => itemAppliesToRepo(s, repo));
  const devNames = devServers.flatMap((s) => cleanArray(s.details.servers));
  const features = Object.keys(d.features || {});
  const mcpPresets = cleanArray(d.mcp_presets);

  const stats: Array<[string, number]> = [
    ['Skills', caps.globalSkills.length + caps.repoSkills.length],
    ['Plugins', caps.globalPlugins.length + caps.repoPlugins.length],
    ['MCP', caps.globalMcp.length + caps.directMcp.length],
    ['Hooks', caps.globalHooks.length + caps.repoHooks.length],
    ['Dev', devNames.length],
  ];

  return (
    <div className="re-detail-inner">
      <header className="re-detail-head">
        <h2>{repo.name}</h2>
        <code className="re-path">{d.path || repo.name}</code>
        <div className="re-pills">
          <ConfigPill label="model" value={d.model} />
          <ConfigPill label="effort" value={d.reasoning} />
          <ConfigPill label="plan" value={d.plan_reasoning as string | undefined} />
          <ConfigPill label="tier" value={d.service_tier as string | undefined} />
          <ConfigPill label="verbosity" value={d.verbosity as string | undefined} />
          <ConfigPill label="personality" value={d.personality as string | undefined} />
        </div>
      </header>

      <div className="re-stats">
        {stats.map(([label, n]) => (
          <div className="re-stat" key={label}>
            <div className="re-stat-n">{n}</div>
            <div className="re-stat-l">{label}</div>
          </div>
        ))}
      </div>

      <CapGroup title="Runtime config" runtime="Codex" count={mcpPresets.length + features.length}>
        <div className="re-config">
          <Chips items={mcpPresets.map((p) => `mcp: ${p}`)} empty="No repo MCP presets" />
          {features.length ? <Chips items={features} accent empty="" /> : null}
        </div>
      </CapGroup>

      <CapGroup
        title="Skills"
        runtime="Codex + Claude"
        count={caps.globalSkills.length + caps.repoSkills.length}
      >
        <p className="re-base">
          Base kit: <strong>{caps.globalSkills.length}</strong> global skills
        </p>
        <Chips items={caps.repoSkills.map((i) => i.title || i.name)} accent empty="No repo-scoped skills — base only" />
      </CapGroup>

      <CapGroup title="Plugins" runtime="Codex" count={caps.globalPlugins.length + caps.repoPlugins.length}>
        <p className="re-base">
          Base kit: <strong>{caps.globalPlugins.length}</strong> global plugins
        </p>
        <Chips items={caps.repoPlugins.map((i) => i.title || i.name)} accent empty="No repo-scoped plugins" />
      </CapGroup>

      <CapGroup title="Tools · MCP" runtime="Codex" count={caps.globalMcp.length + caps.directMcp.length}>
        <p className="re-base">
          Base kit: <strong>{caps.globalMcp.length}</strong> global presets
        </p>
        <Chips items={caps.directMcp.map((i) => i.name)} accent empty="No repo-direct MCP" />
      </CapGroup>

      <CapGroup
        title="Lifecycle · Hooks"
        runtime="Codex · Stop on Claude"
        count={caps.globalHooks.length + caps.repoHooks.length}
      >
        <Chips
          items={[
            ...caps.globalHooks.map((i) => i.title || i.name),
            ...caps.repoHooks.map((i) => i.title || i.name),
          ]}
          empty="No hooks"
        />
      </CapGroup>

      <CapGroup title="Dev & Preview" runtime="Claude" count={devNames.length}>
        <Chips items={devNames} accent empty="No dev servers — add in dev-servers/registry.json" />
      </CapGroup>
    </div>
  );
}

export function RepoExplorer({
  data,
  query,
  initialRepoKey,
}: {
  data: ControlPlaneData;
  query: string;
  initialRepoKey: string;
}) {
  const repos = filteredRepos(data, 'all', query);
  const [selectedKey, setSelectedKey] = useState(initialRepoKey);
  const selected =
    repos.find((r) => repoKey(r.name) === (selectedKey || initialRepoKey)) ?? repos[0];

  return (
    <div className="repo-explorer">
      <aside className="re-list">
        <div className="re-list-head">
          <span>Repos</span>
          <strong>{repos.length}</strong>
        </div>
        <ul>
          {repos.map((repo) => {
            const caps = repoCapabilitySummary(data, repo);
            const dev = data.groups.dev_servers.some((s) => itemAppliesToRepo(s, repo));
            const isSel = selected && repoKey(repo.name) === repoKey(selected.name);
            return (
              <li key={repo.id}>
                <button
                  type="button"
                  className={`re-list-item${isSel ? ' active' : ''}`}
                  onClick={() => setSelectedKey(repoKey(repo.name))}
                >
                  <span className="re-list-name">{repo.name}</span>
                  <span className="re-list-meta">
                    +{caps.localTotal}
                    {dev ? <span className="re-list-dev" title="has dev server" /> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>
      <div className="re-detail">
        {selected ? (
          <RepoDetail data={data} repo={selected} />
        ) : (
          <div className="empty-state">
            <p>No repos match this search.</p>
          </div>
        )}
      </div>
    </div>
  );
}
