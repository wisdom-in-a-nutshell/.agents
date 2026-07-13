import { useState } from 'react';
import { useNavigateItem } from '../primitives';
import { cleanArray, itemAppliesToRepo, repoCapabilitySummary, repoKey } from '../selectors';
import type { ControlPlaneData, Item, SectionId } from '../types';

function Badge({ text }: { text: string }) {
  return <span className="re-badge">{text}</span>;
}

// Count ringed in its scope colour (gold = global base kit, sage = repo's own),
// so the base-kit line reads as its own legend for the chips below.
function ScopeCount({ n, scope }: { n: number; scope: 'global' | 'local' }) {
  return <span className={`re-count ${scope}`}>{n}</span>;
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

// Global base-kit items (gold) + this repo's own additions (sage), one scannable
// row: every inherited capability is named here, color-coded by scope. Each chip
// links to that item in its catalog (scrolled to + highlighted).
function ScopedChips({
  global,
  local,
  kind,
  empty,
}: {
  global: Item[];
  local: Item[];
  kind: SectionId;
  empty: string;
}) {
  const navItem = useNavigateItem();
  if (global.length === 0 && local.length === 0) return <span className="re-empty">{empty}</span>;
  return (
    <div className="re-chips">
      {global.map((it, i) => (
        <button
          key={`g-${it.name}-${i}`}
          type="button"
          className="re-chip global"
          onClick={() => navItem(kind, it.name)}
        >
          {it.title || it.name}
        </button>
      ))}
      {local.map((it, i) => (
        <button
          key={`l-${it.name}-${i}`}
          type="button"
          className="re-chip accent"
          onClick={() => navItem(kind, it.name)}
        >
          {it.title || it.name}
        </button>
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

  const stats: Array<[string, number]> = [
    ['Skills', caps.globalSkills.length + caps.repoSkills.length],
    ['Plugins', caps.globalPlugins.length],
    ['MCP', caps.globalMcp.length + caps.directMcp.length],
    ['Hooks', caps.globalHooks.length + caps.repoHooks.length],
    ['Preview', devNames.length],
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
          <div className={`re-stat${n === 0 ? ' is-zero' : ''}`} key={label}>
            <div className="re-stat-n">{n}</div>
            <div className="re-stat-l">{label}</div>
          </div>
        ))}
      </div>

      <CapGroup title="Runtime config" runtime="Codex" count={features.length}>
        <div className="re-config">
          <Chips items={features} accent empty="No repo runtime feature overrides" />
        </div>
      </CapGroup>

      <CapGroup
        title="Skills"
        runtime="Codex + Claude + Copilot"
        count={caps.globalSkills.length + caps.repoSkills.length}
      >
        <p className="re-base">
          Base kit: <ScopeCount n={caps.globalSkills.length} scope="global" /> global skills
          {caps.repoSkills.length ? <> · <ScopeCount n={caps.repoSkills.length} scope="local" /> repo</> : null}
        </p>
        <ScopedChips global={caps.globalSkills} local={caps.repoSkills} kind="skills" empty="No skills" />
      </CapGroup>

      <CapGroup title="Plugins" runtime="Codex" count={caps.globalPlugins.length}>
        <p className="re-base">
          Base kit: <ScopeCount n={caps.globalPlugins.length} scope="global" /> global plugins
        </p>
        <ScopedChips global={caps.globalPlugins} local={[]} kind="plugins" empty="No plugins" />
      </CapGroup>

      <CapGroup title="Tools · MCP" runtime="Target matrix" count={caps.globalMcp.length + caps.directMcp.length}>
        <p className="re-base">
          Availability can differ across Codex, Claude, and Copilot. Open MCP to inspect the matrix.
        </p>
        <ScopedChips global={caps.globalMcp} local={caps.directMcp} kind="mcp" empty="No MCP presets" />
      </CapGroup>

      <CapGroup
        title="Lifecycle · Hooks"
        runtime="Codex · Stop on Claude"
        count={caps.globalHooks.length + caps.repoHooks.length}
      >
        <ScopedChips global={caps.globalHooks} local={caps.repoHooks} kind="hooks" empty="No hooks" />
      </CapGroup>

      <CapGroup title="Agent Preview" runtime="Codex + Claude + Copilot" count={devNames.length}>
        <Chips items={devNames} accent empty="No preview server. Add in dev-servers/registry.json" />
      </CapGroup>
    </div>
  );
}

export function RepoExplorer({
  data,
  initialRepoKey,
}: {
  data: ControlPlaneData;
  initialRepoKey: string;
}) {
  const repos = data.groups.repos;
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
        <p className="re-list-legend">
          <span>
            <b>+N</b> repo additions
          </span>
        </p>
        <ul>
          {repos.map((repo) => {
            const caps = repoCapabilitySummary(data, repo);
            const isSel = selected && repoKey(repo.name) === repoKey(selected.name);
            return (
              <li key={repo.id}>
                <button
                  type="button"
                  className={`re-list-item${isSel ? ' active' : ''}`}
                  onClick={() => setSelectedKey(repoKey(repo.name))}
                >
                  <span className="re-list-name">{repo.name}</span>
                  <span className={`re-list-meta${caps.localTotal > 0 ? ' has-add' : ''}`}>
                    +{caps.localTotal}
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
            <p>No repos to show.</p>
          </div>
        )}
      </div>
    </div>
  );
}
