import { ChipBlock, EntityMain, RenderPanels, RowActions } from './primitives';
import { compact, filterAttentionItems, labelForScope } from './selectors';
import type { AttentionType, ControlPlaneData, Item, SectionId } from './types';

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

function Attention({ data, filter }: SectionProps) {
  const items = filterAttentionItems(data, filter, '', false);
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

export interface SectionProps {
  data: ControlPlaneData;
  filter: string;
}

export function SectionView({ section: _section, ...props }: SectionProps & { section: SectionId }) {
  return <Attention {...props} />;
}
