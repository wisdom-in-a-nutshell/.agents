import {
  AvailabilityBlock,
  ChipBlock,
  EntityMain,
  McpAvailabilityBlock,
  RenderPanels,
  RowActions,
} from './primitives';
import {
  cleanArray,
  compact,
  filterAttentionItems,
  filteredItems,
  labelForScope,
  scopeHas,
  titleCase,
} from './selectors';
import type { AttentionType, ControlPlaneData, Item, SectionId } from './types';

// ---- Shared rows ---------------------------------------------------------
function SkillRow(item: Item) {
  const path = item.details.source_path || item.details.repo || '';
  const subtitle = compact([titleCase(item.details.origin), labelForScope(item), item.status]).join(' / ');
  return (
    <article key={item.id} className="entity-row">
      <EntityMain title={item.title} subtitle={subtitle} path={path || undefined} />
      <AvailabilityBlock item={item} />
      <RowActions item={item} />
    </article>
  );
}

function PluginRow(item: Item) {
  const subtitle = compact([
    item.details.marketplace,
    item.details.category,
    labelForScope(item),
    item.status,
  ]).join(' / ');
  return (
    <article key={item.id} className="entity-row">
      <EntityMain title={item.title} subtitle={subtitle} />
      <AvailabilityBlock item={item} />
      <RowActions item={item} />
    </article>
  );
}

function McpRow(item: Item) {
  const subtitle = compact([item.details.transport, item.details.url]).join(' / ') || item.status;
  return (
    <article key={item.id} className="entity-row mcp-row">
      <EntityMain title={item.title} subtitle={subtitle} />
      <McpAvailabilityBlock item={item} />
      <RowActions item={item} />
    </article>
  );
}

function HookRow(item: Item) {
  const runtimes = cleanArray(item.details.runtimes).join(', ');
  const subtitle = compact([
    item.details.event,
    runtimes,
    item.details.timeout ? `${item.details.timeout}s` : '',
  ]).join(' / ');
  return (
    <article key={item.id} className="entity-row">
      <EntityMain title={item.title} subtitle={subtitle} />
      <AvailabilityBlock item={item} />
      <RowActions item={item} />
    </article>
  );
}

const ATTENTION_REASON: Record<AttentionType, string> = {
  warnings: 'Review',
  unassigned: 'Not used by global, repo, or plugin config',
  disabled: 'Disabled',
  dormant: 'Dormant',
  unscoped: 'Repo scope without repos',
};

function AttentionRow(item: Item) {
  if (item.kind === 'warning') {
    return (
      <article key={item.id} className="entity-row attention-row">
        <EntityMain title={item.title} subtitle={compact([item.details.code, item.source]).join(' / ')} />
        <ChipBlock values={[item.status]} tone="warning" />
        <div className="row-actions" />
      </article>
    );
  }
  const subtitle = compact([item.kind.toUpperCase(), labelForScope(item), item.status]).join(' / ');
  const reason = ATTENTION_REASON[item.attentionType ?? 'warnings'] ?? 'Review';
  return (
    <article key={item.id} className="entity-row attention-row">
      <EntityMain title={item.title} subtitle={subtitle} />
      <ChipBlock values={[reason]} tone="warning" />
      <RowActions item={item} />
    </article>
  );
}

// ---- Catalog sections ----------------------------------------------------
function Attention({ data, filter, query }: SectionProps) {
  const items = filterAttentionItems(data, filter, query, true);
  const groups: Array<{ title: string; type: AttentionType }> = [
    { title: 'Registry warnings', type: 'warnings' },
    { title: 'Unassigned MCP definitions', type: 'unassigned' },
    { title: 'Disabled capabilities', type: 'disabled' },
    { title: 'Dormant skills', type: 'dormant' },
    { title: 'Missing repo assignments', type: 'unscoped' },
  ];
  return (
    <RenderPanels
      groups={groups.map((g) => ({ title: g.title, items: items.filter((i) => i.attentionType === g.type) }))}
      renderRow={AttentionRow}
      emptyMessage="Nothing needs attention in this view."
    />
  );
}

function Skills({ data, filter, query }: SectionProps) {
  const items = filteredItems(data, 'skills', filter, query);
  return (
    <RenderPanels
      groups={[
        { title: 'Global skills', items: items.filter((i) => i.scope === 'global') },
        { title: 'Repo-scoped skills', items: items.filter((i) => i.scope === 'repo') },
        { title: 'Repo-local skills', items: items.filter((i) => i.scope === 'repo-local') },
        { title: 'Dormant skills', items: items.filter((i) => i.status === 'dormant') },
      ]}
      renderRow={SkillRow}
      emptyMessage="No skills match this view."
    />
  );
}

function Plugins({ data, filter, query }: SectionProps) {
  const items = filteredItems(data, 'plugins', filter, query);
  return (
    <RenderPanels
      groups={[
        { title: 'Enabled global plugins', items: items.filter((i) => i.scope === 'global' && i.status === 'enabled') },
        { title: 'Repo-scoped plugins', items: items.filter((i) => i.scope === 'repo') },
        { title: 'Repo-local plugins', items: items.filter((i) => i.scope === 'repo-local') },
        { title: 'Disabled plugins', items: items.filter((i) => i.status === 'disabled') },
      ]}
      renderRow={PluginRow}
      emptyMessage="No plugins match this view."
    />
  );
}

function Mcp({ data, filter, query }: SectionProps) {
  const items = filteredItems(data, 'mcp', filter, query);
  return (
    <RenderPanels
      groups={[
        { title: 'Global MCP presets', items: items.filter((i) => scopeHas(i, 'global')) },
        { title: 'Repo MCP presets', items: items.filter((i) => !scopeHas(i, 'global') && scopeHas(i, 'repo')) },
        {
          title: 'Plugin MCP presets',
          items: items.filter((i) => !scopeHas(i, 'global') && !scopeHas(i, 'repo') && scopeHas(i, 'plugin')),
        },
        { title: 'Unassigned MCP definitions', items: items.filter((i) => i.scope === 'unassigned') },
      ]}
      renderRow={McpRow}
      emptyMessage="No MCP presets match this view."
    />
  );
}

function Hooks({ data, filter, query }: SectionProps) {
  const items = filteredItems(data, 'hooks', filter, query);
  return (
    <RenderPanels
      groups={[
        { title: 'Global hooks', items: items.filter((i) => i.scope === 'global') },
        { title: 'Repo hooks', items: items.filter((i) => i.scope === 'repo') },
        { title: 'Disabled hooks', items: items.filter((i) => i.status === 'disabled') },
      ]}
      renderRow={HookRow}
      emptyMessage="No hooks match this view."
    />
  );
}

export interface SectionProps {
  data: ControlPlaneData;
  filter: string;
  query: string;
  focusedRepoKey: string;
}

export function SectionView({ section, ...props }: SectionProps & { section: SectionId }) {
  switch (section) {
    case 'skills':
      return <Skills {...props} />;
    case 'plugins':
      return <Plugins {...props} />;
    case 'mcp':
      return <Mcp {...props} />;
    case 'hooks':
      return <Hooks {...props} />;
    default:
      return <Attention {...props} />;
  }
}
