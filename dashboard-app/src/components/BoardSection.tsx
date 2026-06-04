import { formatDate, repoDisplayName } from '../selectors';
import { useNavigateRepo } from '../primitives';
import type { Capability, ControlPlaneData, Item, RuntimeCell } from '../types';

const STATUS_LABEL: Record<RuntimeCell['status'], string> = {
  stable: 'Stable',
  new: 'New',
  planned: 'Planned',
  na: 'not applicable',
};

function Cell({ cell }: { cell: RuntimeCell }) {
  return (
    <div className="cp-cell">
      <span className={`cp-chip ${cell.status}`}>
        {cell.status !== 'na' ? <span className="cp-b" /> : null}
        {STATUS_LABEL[cell.status]}
      </span>
      {cell.note ? <span className="cp-note">{cell.note}</span> : null}
    </div>
  );
}

function Board({ capabilities }: { capabilities: Capability[] }) {
  return (
    <div className="cp-board">
      <div className="cp-row cp-head">
        <div>Capability</div>
        <div>Codex</div>
        <div>Claude</div>
        <div>Source</div>
      </div>
      {capabilities.map((cap) => (
        <div className="cp-row" key={cap.key}>
          <div className="cp-cap">
            <div className="cp-cap-name">
              {cap.name}
              {cap.count != null ? <span className="cp-count">{cap.count}</span> : null}
            </div>
            <div className="cp-cap-desc">{cap.desc}</div>
          </div>
          <Cell cell={cap.codex} />
          <Cell cell={cap.claude} />
          <div className="cp-cell cp-src">
            <code>{cap.source}</code>
          </div>
        </div>
      ))}
    </div>
  );
}

function RepoCoverage({ repos }: { repos: Item[] }) {
  const navigate = useNavigateRepo();
  const maxSkills = Math.max(1, ...repos.map((r) => r.details.skill_count ?? 0));
  return (
    <table className="cp-repos">
      <thead>
        <tr>
          <th>Repo</th>
          <th className="cp-num">Skills</th>
          <th className="cp-num">Plugins</th>
          <th className="cp-num">MCP</th>
          <th className="cp-num">Hooks</th>
          <th className="cp-center">Dev</th>
        </tr>
      </thead>
      <tbody>
        {repos.map((repo) => {
          const skills = repo.details.skill_count ?? 0;
          const mcp = repo.details.mcp_count ?? 0;
          const dev = repo.details.dev_count ?? 0;
          const w = Math.round((skills / maxSkills) * 46);
          return (
            <tr key={repo.id}>
              <td className="cp-repo">
                <button type="button" className="cp-repo-link" onClick={() => navigate(repo.name)}>
                  {repoDisplayName(repo.name)}
                </button>
              </td>
              <td className="cp-num">
                {skills}
                <span className="cp-bar" style={{ width: `${w}px` }} />
              </td>
              <td className="cp-num">{repo.details.plugin_count ?? 0}</td>
              <td className="cp-num">{mcp || <span className="cp-faint">·</span>}</td>
              <td className="cp-num">{repo.details.hook_count ?? 0}</td>
              <td className="cp-center">
                {dev ? <span className="cp-devdot" title={`${dev} dev server${dev > 1 ? 's' : ''}`} /> : <span className="cp-faint">·</span>}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function BoardSection({ data }: { data: ControlPlaneData }) {
  const caps = data.capabilities ?? [];
  const c = data.counts;
  const stats: Array<[number, string]> = [
    [c.skills, 'Skills'],
    [c.plugins, 'Plugins'],
    [c.mcp, 'MCP tools'],
    [c.hooks, 'Hooks'],
    [c.repos, 'Repos'],
    [c.dev_servers, 'Dev servers'],
  ];
  return (
    <div className="cp-wrap">
      <header className="cp-top">
        <div>
          <div className="cp-brand">
            <h1>Control Plane</h1>
            <span className="cp-dot" />
          </div>
          <p className="cp-tagline">
            How the agents are set up to write better code — every capability the runtimes inherit, and which runtime gets it.
          </p>
        </div>
        <div className="cp-meta">
          updated <b>{formatDate(data.generated_at_utc)}</b>
          <br />
          <b>{c.repos}</b> repos · <b>{(data.runtimes ?? []).length}</b> runtimes ·{' '}
          <b className={c.warnings ? 'cp-warn' : ''}>{c.warnings}</b> warnings
        </div>
      </header>

      <div className="cp-stats">
        {stats.map(([n, label]) => (
          <div className="cp-stat" key={label}>
            <div className="cp-n">{n}</div>
            <div className="cp-l">{label}</div>
          </div>
        ))}
      </div>

      <div className="cp-sec-head">
        <h2>Capabilities × Runtimes</h2>
        <span className="cp-hint">what each lever enables, and where it lands</span>
      </div>
      <Board capabilities={caps} />
      <div className="cp-legend">
        <span><span className="cp-b" style={{ background: 'var(--accent)' }} />Stable — wired &amp; in use</span>
        <span><span className="cp-b" style={{ background: 'var(--amber)' }} />New — just landed</span>
        <span><span className="cp-b" style={{ background: 'var(--faint)' }} />Planned — next</span>
        <span><span className="cp-b cp-b-dash" />Not applicable</span>
      </div>

      <div className="cp-sec-head cp-sec-head-2">
        <h2>Repo coverage</h2>
        <span className="cp-hint">what each of the {data.groups.repos.length} managed repos inherits</span>
      </div>
      <RepoCoverage repos={data.groups.repos} />
      <p className="cp-foot">
        Source of truth: the registries under <code>~/.agents</code>. Generated from{' '}
        <code>control-plane-dashboard.py</code> — read-only, no state of its own.
      </p>
    </div>
  );
}
