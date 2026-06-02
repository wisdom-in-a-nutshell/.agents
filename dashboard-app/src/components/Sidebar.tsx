import type { ControlPlaneData, SectionId } from '../types';
import { navCount } from '../selectors';

const NAV: Array<{ id: SectionId; label: string; short: string }> = [
  { id: 'overview', label: 'Overview', short: 'O' },
  { id: 'attention', label: 'Attention', short: '!' },
  { id: 'repos', label: 'Repos', short: 'R' },
  { id: 'skills', label: 'Skills', short: 'S' },
  { id: 'plugins', label: 'Plugins', short: 'P' },
  { id: 'mcp', label: 'MCP', short: 'M' },
  { id: 'hooks', label: 'Hooks', short: 'H' },
];

export function Sidebar({
  data,
  section,
  collapsed,
  query,
  lastUpdated,
  refreshStatus,
  onSelect,
  onToggleCollapse,
  onQueryChange,
}: {
  data: ControlPlaneData | null;
  section: SectionId;
  collapsed: boolean;
  query: string;
  lastUpdated: string;
  refreshStatus: string;
  onSelect: (section: SectionId) => void;
  onToggleCollapse: () => void;
  onQueryChange: (value: string) => void;
}) {
  return (
    <aside className="sidebar" aria-label="Dashboard navigation">
      <div className="sidebar-head">
        <div className="brand-lockup">
          <span>Agent Control</span>
          <strong>.agents</strong>
        </div>
        <button
          className="sidebar-toggle"
          type="button"
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          aria-expanded={!collapsed}
          title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          onClick={onToggleCollapse}
        >
          <span aria-hidden="true">{collapsed ? '>' : '<'}</span>
        </button>
      </div>

      <nav className="nav-stack" aria-label="Control-plane sections">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-button${section === item.id ? ' active' : ''}`}
            onClick={() => onSelect(item.id)}
          >
            <span className="nav-label">{item.label}</span>
            <span className="nav-short" aria-hidden="true">
              {item.short}
            </span>
            <strong>{data ? navCount(data, item.id) : 0}</strong>
          </button>
        ))}
      </nav>

      <label className="search-box sidebar-search">
        <span>Search</span>
        <input
          type="search"
          placeholder="Search names, repos, paths"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
        />
      </label>

      <div className="sidebar-footer">
        <span>{lastUpdated}</span>
        <span>{refreshStatus}</span>
      </div>
    </aside>
  );
}
