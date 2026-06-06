import { createContext, type ReactNode, useContext } from 'react';
import { sourceHref, sourceLabel } from './selectors';
import type { Item, SectionId, Tone } from './types';

// Repo navigation is needed deep inside rows/chips; carry it via context.
const NavContext = createContext<(repoName: string) => void>(() => {});
export const NavProvider = NavContext.Provider;
export function useNavigateRepo(): (repoName: string) => void {
  return useContext(NavContext);
}

// Catalog-item navigation (repo detail chip → its skill/plugin/mcp/hook in the
// catalog, scrolled to and highlighted). Same plumbing, different target.
const NavItemContext = createContext<(section: SectionId, name: string) => void>(() => {});
export const NavItemProvider = NavItemContext.Provider;
export function useNavigateItem(): (section: SectionId, name: string) => void {
  return useContext(NavItemContext);
}

function cx(...parts: Array<string | false | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

export function Chip({ text, tone = '', scopeTone = '' }: { text: string; tone?: Tone | ''; scopeTone?: Tone | '' }) {
  return <span className={cx('chip', tone, scopeTone)}>{text}</span>;
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

export function RowActions({ item }: { item: Item }) {
  return (
    <div className="row-actions">
      <a
        href={sourceHref(item)}
        target="_blank"
        rel="noreferrer"
        aria-label={`${item.name} source (opens in new tab)`}
      >
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
