import {
  countForFilter,
  filterOptions,
  metricsForSection,
  rootName,
  scopeToneForFilter,
  sectionMeta,
} from '../selectors';
import type { ControlPlaneData, SectionId } from '../types';

export function Topbar({ data, section }: { data: ControlPlaneData; section: SectionId }) {
  const meta = sectionMeta[section];
  const sources = Object.keys(data.sources || {}).length;
  const warnings = data.counts.warnings;
  return (
    <header className="topbar">
      <div className="section-title">
        <p className="eyebrow">{meta.eyebrow}</p>
        <h2>{meta.title}</h2>
      </div>
      <div className="topbar-meta" aria-label="Control-plane status">
        <Pill label="Root" value={rootName(data.repo_root)} />
        <Pill label="Sources" value={sources} />
        <Pill label="Warnings" value={warnings} tone={warnings ? 'warning' : 'ok'} />
      </div>
    </header>
  );
}

function Pill({ label, value, tone = '' }: { label: string; value: string | number; tone?: string }) {
  return (
    <span className={`topbar-pill${tone ? ` ${tone}` : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

export function MetricsGrid({ data, section }: { data: ControlPlaneData; section: SectionId }) {
  const metrics = metricsForSection(data, section);
  return (
    <section className="metrics-grid" aria-label="Section totals">
      {metrics.map((m) => (
        <article key={m.label} className={`metric-block${m.tone ? ` ${m.tone}` : ''}`}>
          <span>{m.label}</span>
          <strong>{m.value}</strong>
        </article>
      ))}
    </section>
  );
}

export function WarningsPanel({ data, section }: { data: ControlPlaneData; section: SectionId }) {
  const warnings = data.warnings;
  if (warnings.length === 0 || section === 'attention') return null;
  return (
    <section className="warning-panel" aria-label="Registry warnings">
      <div className="panel-heading">
        <h2>Warnings</h2>
        <span>{warnings.length}</span>
      </div>
      <div className="warning-list">
        {warnings.slice(0, 8).map((w, i) => (
          <div key={`${w.code}-${i}`} className={`warning-item${w.severity === 'error' ? ' error' : ''}`}>
            <strong>{w.message}</strong>
            <span>
              {w.code} / {w.source}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function FilterBar({
  data,
  section,
  filter,
  onSelect,
}: {
  data: ControlPlaneData;
  section: SectionId;
  filter: string;
  onSelect: (filter: string) => void;
}) {
  const options = filterOptions[section] || filterOptions.overview;
  const visible = options.filter((o) => o.id === 'all' || countForFilter(data, section, o.id) > 0);
  if (visible.length <= 1) return null;
  return (
    <section className="filter-bar" aria-label="Section filters">
      {visible.map((o) => {
        const tone = scopeToneForFilter(o.id);
        const active = filter === o.id;
        return (
          <button
            key={o.id}
            type="button"
            className={`filter-chip${tone ? ` ${tone}` : ''}${active ? ' active' : ''}`}
            onClick={() => onSelect(o.id)}
          >
            <span>{o.label}</span>
            <strong>{countForFilter(data, section, o.id)}</strong>
          </button>
        );
      })}
    </section>
  );
}
