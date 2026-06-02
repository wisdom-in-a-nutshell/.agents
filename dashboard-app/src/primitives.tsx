import { createContext, type ReactNode, useContext } from 'react';
import {
  cleanArray,
  repoDisplayName,
  scopeHas,
  scopeToneForItem,
  sourceHref,
  sourceLabel,
} from './selectors';
import type { Item, Tone } from './types';

// Repo navigation is needed deep inside rows/chips; carry it via context.
const NavContext = createContext<(repoName: string) => void>(() => {});
export const NavProvider = NavContext.Provider;
export function useNavigateRepo(): (repoName: string) => void {
  return useContext(NavContext);
}

function cx(...parts: Array<string | false | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

export function Chip({ text, tone = '', scopeTone = '' }: { text: string; tone?: Tone | ''; scopeTone?: Tone | '' }) {
  return <span className={cx('chip', tone, scopeTone)}>{text}</span>;
}

export function RepoChip({ name, scopeTone = '' }: { name: string; scopeTone?: Tone | '' }) {
  const navigate = useNavigateRepo();
  return (
    <button
      type="button"
      className={cx('chip', 'repo-link', scopeTone)}
      title={`Show ${repoDisplayName(name)} in Repos`}
      onClick={(event) => {
        event.stopPropagation();
        navigate(name);
      }}
    >
      {repoDisplayName(name)}
    </button>
  );
}

export function EntityMain({
  title,
  subtitle,
  path,
}: {
  title: string;
  subtitle?: string;
  path?: string;
}) {
  return (
    <div className="entity-main">
      <h3>{title}</h3>
      {subtitle ? <p>{subtitle}</p> : null}
      {path ? <p className="entity-path">{path}</p> : null}
    </div>
  );
}

export function StatLine({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-line">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function SmallCount({ label, value, tone = '' }: { label: string; value: number; tone?: Tone | '' }) {
  return (
    <span className={cx('small-count', tone)}>
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

export function RuntimePill({ text }: { text: string }) {
  return <span className="runtime-pill">{text}</span>;
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="empty-state">
      <p>{message}</p>
    </div>
  );
}

export function ChipBlock({ values, tone = '' }: { values: string[]; tone?: Tone | '' }) {
  return (
    <div className="availability-block">
      {values.map((v, i) => (
        <Chip key={`${v}-${i}`} text={v} tone={tone} />
      ))}
    </div>
  );
}

export function AvailabilityBlock({ item }: { item: Item }) {
  if (item.scope === 'global') {
    return (
      <div className="availability-block">
        <Chip text="All repos" scopeTone="scope-global" />
      </div>
    );
  }
  if (item.status === 'dormant' || item.scope === 'dormant') {
    return (
      <div className="availability-block">
        <Chip text="Dormant" tone="warning" />
      </div>
    );
  }
  const repos = cleanArray(item.repos);
  if (repos.length === 0) {
    return (
      <div className="availability-block">
        <span className="muted">No repo assignment</span>
      </div>
    );
  }
  const tone = scopeToneForItem(item);
  return (
    <div className="availability-block">
      {repos.map((r, i) => (
        <RepoChip key={`${r}-${i}`} name={r} scopeTone={tone} />
      ))}
    </div>
  );
}

export function McpAvailabilityBlock({ item }: { item: Item }) {
  const children: ReactNode[] = [];
  if (scopeHas(item, 'global')) {
    children.push(<Chip key="global" text="Global" scopeTone="scope-global" />);
  }
  cleanArray(item.repos).forEach((r, i) => {
    children.push(<RepoChip key={`repo-${r}-${i}`} name={r} scopeTone="scope-local" />);
  });
  cleanArray(item.details.plugins).forEach((p, i) => {
    children.push(<Chip key={`plugin-${p}-${i}`} text={`Plugin: ${p}`} />);
  });
  if (children.length === 0) {
    children.push(<Chip key="unassigned" text="Unassigned" tone="warning" />);
  }
  return <div className="availability-block">{children}</div>;
}

export function RowActions({ item }: { item: Item }) {
  return (
    <div className="row-actions">
      <a href={sourceHref(item)} target="_blank" rel="noreferrer">
        {sourceLabel(item)}
      </a>
    </div>
  );
}

export function GroupedPanel({
  title,
  items,
  renderRow,
  emptyMessage,
}: {
  title: string;
  items: Item[];
  renderRow: (item: Item) => ReactNode;
  emptyMessage: string;
}) {
  return (
    <section className="section-panel">
      <div className="panel-heading">
        <h2>{title}</h2>
        <span>{items.length}</span>
      </div>
      <div className="row-stack">
        {items.length ? items.map(renderRow) : <EmptyState message={emptyMessage} />}
      </div>
    </section>
  );
}

/** Render one grouped panel per non-empty group; fall back to a single empty state. */
export function RenderPanels({
  groups,
  renderRow,
  emptyMessage,
}: {
  groups: Array<{ title: string; items: Item[] }>;
  renderRow: (item: Item) => ReactNode;
  emptyMessage: string;
}) {
  const present = groups.filter((g) => g.items.length > 0);
  if (present.length === 0) return <EmptyState message={emptyMessage} />;
  return (
    <>
      {present.map((g) => (
        <GroupedPanel
          key={g.title}
          title={g.title}
          items={g.items}
          renderRow={renderRow}
          emptyMessage={emptyMessage}
        />
      ))}
    </>
  );
}
