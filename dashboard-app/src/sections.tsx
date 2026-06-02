import {
  AvailabilityBlock,
  Chip,
  ChipBlock,
  EmptyState,
  EntityMain,
  GroupedPanel,
  McpAvailabilityBlock,
  RenderPanels,
  RowActions,
  RuntimePill,
  SmallCount,
  StatLine,
  useNavigateRepo,
} from './primitives';
import {
  type CapabilitySummary,
  cleanArray,
  compact,
  disabledItems,
  dormantSkills,
  enabledGlobalHooks,
  enabledGlobalPlugins,
  filterAttentionItems,
  filteredItems,
  filteredRepos,
  globalMcp,
  globalSkills,
  labelForScope,
  missingRepoAssignments,
  repoCapabilitySummary,
  repoDirectMcpForRepo,
  repoScopedPluginsForRepo,
  repoScopedSkillsForRepo,
  scopeHas,
  sourceLabels,
  sourceOrder,
  titleCase,
  unassignedMcp,
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

// ---- Repo pieces ---------------------------------------------------------
function CapabilityBlock({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: Item[];
  emptyText: string;
}) {
  return (
    <section className="capability-block scope-local">
      <div className="capability-heading">
        <h3>{title}</h3>
        <strong>{items.length}</strong>
      </div>
      <div className="chip-list">
        {items.length ? (
          items.map((i) => <Chip key={i.id} text={i.title || i.name} scopeTone="scope-local" />)
        ) : (
          <span className="muted">{emptyText}</span>
        )}
      </div>
    </section>
  );
}

function RepoCard({ repo, caps, focused }: { repo: Item; caps: CapabilitySummary; focused: boolean }) {
  return (
    <article
      className={`repo-card${focused ? ' repo-card-focused' : ''}`}
      data-repo-key={repo.name.toLowerCase()}
      tabIndex={-1}
    >
      <div className="repo-card-head">
        <EntityMain title={repo.name} subtitle={repo.details.path || repo.name} />
        <div className="repo-runtime">
          <RuntimePill text={repo.details.model || 'default model'} />
          <RuntimePill text={`reasoning ${repo.details.reasoning || 'default'}`} />
        </div>
      </div>
      <div className="base-kit">
        <SmallCount label="Global skills" value={caps.globalSkills.length} tone="scope-global" />
        <SmallCount label="Global plugins" value={caps.globalPlugins.length} tone="scope-global" />
        <SmallCount label="Global hooks" value={caps.globalHooks.length} tone="scope-global" />
        <SmallCount label="Global MCP" value={caps.globalMcp.length} tone="scope-global" />
      </div>
      <div className="capability-grid">
        <CapabilityBlock title="Repo skills" items={caps.repoSkills} emptyText="Base only" />
        <CapabilityBlock title="Repo plugins" items={caps.repoPlugins} emptyText="None" />
        <CapabilityBlock title="MCP" items={caps.directMcp} emptyText="None" />
        <CapabilityBlock title="Repo hooks" items={caps.repoHooks} emptyText="Global only" />
      </div>
    </article>
  );
}

function RepoOverviewRow({ repo, caps }: { repo: Item; caps: CapabilitySummary }) {
  const navigate = useNavigateRepo();
  return (
    <article
      className="compact-row repo-overview-row clickable-row"
      role="button"
      tabIndex={0}
      title={`Show ${repo.name} in Repos`}
      onClick={() => navigate(repo.name)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          navigate(repo.name);
        }
      }}
    >
      <EntityMain title={repo.name} subtitle={repo.details.path || repo.name} />
      <div className="mini-totals">
        <SmallCount label="Base" value={caps.baseTotal} tone="scope-global" />
        <SmallCount label="Local" value={caps.localTotal} tone="scope-local" />
        <SmallCount label="MCP" value={caps.directMcp.length} tone="scope-local" />
      </div>
    </article>
  );
}

function SourcePanel({ data }: { data: ControlPlaneData }) {
  const sources = data.sources || {};
  const keys = sourceOrder.filter((k) => sources[k]);
  return (
    <section className="section-panel source-panel">
      <div className="panel-heading">
        <h2>Canonical sources</h2>
        <span>{Object.keys(sources).length}</span>
      </div>
      <div className="source-list">
        {keys.map((key) => {
          const source = sources[key];
          return (
            <a
              key={key}
              className="source-row"
              href={`/source/${source.path}`}
              title={source.absolute_path || source.path}
              target="_blank"
              rel="noreferrer"
            >
              <span>{sourceLabels[key] || titleCase(key)}</span>
              <code>{source.path}</code>
            </a>
          );
        })}
      </div>
    </section>
  );
}

function OverviewPanel({
  title,
  tone,
  lines,
}: {
  title: string;
  tone: '' | 'scope-global' | 'scope-local';
  lines: Array<[string, number]>;
}) {
  return (
    <section className={`overview-panel${tone ? ` ${tone}` : ''}`}>
      <h2>{title}</h2>
      <div className="stat-list">
        {lines.map(([label, value]) => (
          <StatLine key={label} label={label} value={value} />
        ))}
      </div>
    </section>
  );
}

// ---- Sections ------------------------------------------------------------
function Overview({ data, filter, query }: SectionProps) {
  const repos = filteredRepos(data, filter, query).slice(0, 8);
  const allRepos = data.groups.repos;
  const countRepos = (pred: (r: Item) => boolean) => allRepos.filter(pred).length;
  return (
    <>
      <section className="overview-grid">
        <OverviewPanel
          title="Global base kit"
          tone="scope-global"
          lines={[
            ['Skills', globalSkills(data).length],
            ['Plugins', enabledGlobalPlugins(data).length],
            ['Hooks', enabledGlobalHooks(data).length],
            ['MCP', globalMcp(data).length],
          ]}
        />
        <OverviewPanel
          title="Repo-specific additions"
          tone="scope-local"
          lines={[
            ['Repos with skills', countRepos((r) => repoScopedSkillsForRepo(data, r).length > 0)],
            ['Repos with plugins', countRepos((r) => repoScopedPluginsForRepo(data, r).length > 0)],
            ['Repos with MCP', countRepos((r) => repoDirectMcpForRepo(data, r).length > 0)],
            ['Repo-local skills', data.groups.skills.filter((i) => i.scope === 'repo-local').length],
          ]}
        />
        <OverviewPanel
          title="Attention"
          tone=""
          lines={[
            ['Warnings', data.counts.warnings],
            ['Unassigned MCP', unassignedMcp(data).length],
            ['Disabled', disabledItems(data).length],
            ['Dormant', dormantSkills(data).length],
            ['Missing repos', missingRepoAssignments(data).length],
          ]}
        />
      </section>
      <SourcePanel data={data} />
      <GroupedPanel
        title="Repos with the most local shape"
        items={repos}
        renderRow={(repo) => (
          <RepoOverviewRow key={repo.id} repo={repo} caps={repoCapabilitySummary(data, repo)} />
        )}
        emptyMessage="No repos match this search."
      />
    </>
  );
}

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

function Repos({ data, filter, query, focusedRepoKey }: SectionProps) {
  const repos = filteredRepos(data, filter, query);
  if (repos.length === 0) return <EmptyState message="No repos match this view." />;
  return (
    <div className="repo-list-view">
      {repos.map((repo) => (
        <RepoCard
          key={repo.id}
          repo={repo}
          caps={repoCapabilitySummary(data, repo)}
          focused={Boolean(focusedRepoKey) && repo.name.toLowerCase() === focusedRepoKey}
        />
      ))}
    </div>
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
    case 'attention':
      return <Attention {...props} />;
    case 'repos':
      return <Repos {...props} />;
    case 'skills':
      return <Skills {...props} />;
    case 'plugins':
      return <Plugins {...props} />;
    case 'mcp':
      return <Mcp {...props} />;
    case 'hooks':
      return <Hooks {...props} />;
    default:
      return <Overview {...props} />;
  }
}
