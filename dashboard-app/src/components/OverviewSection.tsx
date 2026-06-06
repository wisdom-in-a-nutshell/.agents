import { useNavigateRepo } from '../primitives';
import {
  attentionItems,
  disabledItems,
  dormantSkills,
  enabledGlobalHooks,
  enabledGlobalPlugins,
  enabledHooks,
  enabledPlugins,
  globalMcp,
  globalSkills,
  missingRepoAssignments,
  repoCapabilitySummary,
  repoDisplayName,
  unassignedMcp,
} from '../selectors';
import type { ControlPlaneData, SectionId } from '../types';

// The home: a calm answer to "what does every agent inherit, and what needs me?"
// No selection required. Status first, then the base kit, then totals + repos.
export function OverviewSection({
  data,
  onNavigate,
}: {
  data: ControlPlaneData;
  onNavigate: (section: SectionId) => void;
}) {
  const navigateRepo = useNavigateRepo();
  const c = data.counts;

  // The golden light through the canopy: what reaches every repo.
  const base = {
    skills: globalSkills(data).length,
    plugins: enabledGlobalPlugins(data).length,
    mcp: globalMcp(data).length,
    hooks: enabledGlobalHooks(data).length,
  };

  // Warnings are real problems (rose). Everything else is housekeeping (quiet).
  const warnRows = attentionItems(data)
    .filter((i) => i.attentionType === 'warnings')
    .slice(0, 4);
  const warnings = data.warnings.length;
  const housekeeping = [
    { label: 'Unassigned MCP', n: unassignedMcp(data).length },
    { label: 'Disabled', n: disabledItems(data).length },
    { label: 'Dormant skills', n: dormantSkills(data).length },
    { label: 'Missing repo assignments', n: missingRepoAssignments(data).length },
  ].filter((h) => h.n > 0);
  const reviewCount = housekeeping.reduce((sum, h) => sum + h.n, 0);
  const allClear = warnings === 0 && housekeeping.length === 0;

  // Highlight repos that configure something of their own; the base-kit-only
  // tail is one summary line. (Dev servers live on the Board, not the glance.)
  const ranked = data.groups.repos
    .map((r) => ({ repo: r, add: repoCapabilitySummary(data, r).localTotal }))
    .sort((a, b) => b.add - a.add);
  const highlights = ranked.filter((r) => r.add > 0);
  const baseOnly = ranked.length - highlights.length;

  const totals: Array<{ label: string; n: number; section: SectionId }> = [
    { label: 'Skills', n: c.skills, section: 'skills' },
    { label: 'Plugins', n: enabledPlugins(data).length, section: 'plugins' },
    { label: 'MCP tools', n: c.mcp, section: 'mcp' },
    { label: 'Hooks', n: enabledHooks(data).length, section: 'hooks' },
    { label: 'Repos', n: c.repos, section: 'repos' },
  ];

  const statusTone = allClear ? 'ok' : warnings ? 'alert' : 'note';
  const statusText = allClear
    ? 'All clear'
    : warnings
      ? `${warnings} warning${warnings > 1 ? 's' : ''}`
      : `${reviewCount} to review`;

  return (
    <div className="ov-wrap">
      <header className="ov-top">
        <div>
          <h1>Control Plane</h1>
          <p className="ov-tagline">
            Everything your agents inherit, and anything that needs a look.
          </p>
        </div>
        <div className="ov-status">
          <span className={`ov-pill ${statusTone}`}>
            <span className="ov-dot" aria-hidden="true" />
            {statusText}
          </span>
        </div>
      </header>

      <button className="ov-base" type="button" onClick={() => onNavigate('board')}>
        <span className="ov-base-label">Base kit · inherited by every repo</span>
        <span className="ov-base-nums">
          <b>{base.skills}</b> skills <i>·</i> <b>{base.plugins}</b> plugins <i>·</i>{' '}
          <b>{base.mcp}</b> MCP <i>·</i> <b>{base.hooks}</b> hook{base.hooks > 1 ? 's' : ''}
        </span>
        <span className="ov-base-go" aria-hidden="true">→</span>
      </button>

      <section className="ov-needs">
        <div className="ov-sec-head">
          <h2>Needs you</h2>
          <button className="ov-link" type="button" onClick={() => onNavigate('attention')}>
            Open attention →
          </button>
        </div>
        {allClear ? (
          <div className="ov-clear">
            <span className="ov-check" aria-hidden="true" />
            Nothing needs a look. Every capability is wired and assigned.
          </div>
        ) : (
          <div className="ov-needs-body">
            {warnRows.length > 0 ? (
              <div className="ov-warns">
                {warnRows.map((w) => (
                  <button
                    key={w.id}
                    className="ov-warn-row"
                    type="button"
                    onClick={() => onNavigate('attention')}
                  >
                    <span className="ov-warn-title">{w.title}</span>
                    <span className="ov-warn-src">{w.source}</span>
                  </button>
                ))}
              </div>
            ) : null}
            {housekeeping.length > 0 ? (
              <div className="ov-house">
                <span className="ov-house-label">Housekeeping</span>
                {housekeeping.map((h) => (
                  <button
                    key={h.label}
                    className="ov-house-item"
                    type="button"
                    onClick={() => onNavigate('attention')}
                  >
                    {h.label}
                    <strong>{h.n}</strong>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        )}
      </section>

      <section className="ov-block">
        <div className="ov-sec-head">
          <h2>What's installed</h2>
          <span className="ov-hint">click any to explore</span>
        </div>
        <div className="ov-totals">
          {totals.map((t) =>
            t.n === 0 ? (
              <div key={t.label} className="ov-total is-zero">
                <span className="ov-total-n">0</span>
                <span className="ov-total-l">{t.label}</span>
              </div>
            ) : (
              <button
                key={t.label}
                className="ov-total"
                type="button"
                onClick={() => onNavigate(t.section)}
              >
                <span className="ov-total-n">{t.n}</span>
                <span className="ov-total-l">{t.label}</span>
              </button>
            ),
          )}
        </div>
      </section>

      <section className="ov-block">
        <div className="ov-sec-head">
          <h2>{c.repos} repos</h2>
          <span className="ov-legend">
            <span className="ov-key">
              <b>+N</b> repo additions
            </span>
          </span>
          <button className="ov-link" type="button" onClick={() => onNavigate('repos')}>
            Open repos →
          </button>
        </div>
        <div className="ov-repos">
          {highlights.map(({ repo, add }) => (
            <button
              key={repo.id}
              className="ov-repo"
              type="button"
              onClick={() => navigateRepo(repo.name)}
            >
              <span className="ov-repo-name">{repoDisplayName(repo.name)}</span>
              <span className="ov-repo-add">+{add}</span>
            </button>
          ))}
        </div>
        {baseOnly > 0 ? (
          <p className="ov-baseonly">{baseOnly} more inherit the base kit only.</p>
        ) : null}
      </section>
    </div>
  );
}
