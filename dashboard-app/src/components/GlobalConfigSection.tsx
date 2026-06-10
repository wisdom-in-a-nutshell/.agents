import type { ConfigGroup, ControlPlaneData } from '../types';

const RUNTIME_META = {
  codex: {
    title: 'Codex global config',
    hint: 'what every Codex session inherits — rendered to ~/.codex/config.toml',
  },
  claude: {
    title: 'Claude global config',
    hint: 'what every Claude Code session inherits — rendered to ~/.claude/settings.json',
  },
} as const;

export function GlobalConfigSection({
  data,
  runtime,
}: {
  data: ControlPlaneData;
  runtime: 'codex' | 'claude';
}) {
  const meta = RUNTIME_META[runtime];
  const groups: ConfigGroup[] = data.global_config?.[runtime] ?? [];

  return (
    <>
      <div className="cat-head">
        <h2>{meta.title}</h2>
        <span className="cat-hint">{meta.hint}</span>
      </div>

      {groups.length === 0 ? (
        <div className="empty-state">
          <p>No global configuration found for {runtime}.</p>
        </div>
      ) : (
        <div className="gc-grid">
          {groups.map((group) => (
            <section className="gc-card" key={group.title}>
              <header className="gc-card-head">
                <h3>{group.title}</h3>
                <a className="gc-src" href={`/source/${group.source}`} title={group.source}>
                  <code>{group.source}</code>
                </a>
              </header>
              <dl className="gc-rows">
                {group.rows.map((row, i) => (
                  <div className="gc-row" key={`${row.label}-${i}`}>
                    <dt>{row.label}</dt>
                    <dd className={`gc-val${row.tone ? ` gc-${row.tone}` : ''}`}>{row.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
