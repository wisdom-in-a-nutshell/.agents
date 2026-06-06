import type { ControlPlaneData, SectionId } from '../types';
import { navCount } from '../selectors';

type NavItem = { id: SectionId; label: string; short: string };

const NAV_GROUPS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: 'Views',
    items: [
      { id: 'overview', label: 'Overview', short: 'O' },
      { id: 'board', label: 'Board', short: 'B' },
      { id: 'repos', label: 'Repos', short: 'R' },
      { id: 'attention', label: 'Attention', short: '!' },
    ],
  },
  {
    label: 'Catalogs',
    items: [
      { id: 'skills', label: 'Skills', short: 'S' },
      { id: 'plugins', label: 'Plugins', short: 'P' },
      { id: 'mcp', label: 'MCP', short: 'M' },
      { id: 'hooks', label: 'Hooks', short: 'H' },
    ],
  },
];

export function Sidebar({
  data,
  section,
  collapsed,
  loadStatus,
  onSelect,
  onToggleCollapse,
}: {
  data: ControlPlaneData | null;
  section: SectionId;
  collapsed: boolean;
  loadStatus: string;
  onSelect: (section: SectionId) => void;
  onToggleCollapse: () => void;
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
        {NAV_GROUPS.map((group) => (
          <div className="nav-group" key={group.label}>
            <span className="nav-group-label" aria-hidden="true">
              {group.label}
            </span>
            {group.items.map((item) => {
              const count = data ? navCount(data, item.id) : 0;
              return (
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
                  {count > 0 ? <strong>{count}</strong> : null}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {loadStatus ? (
        <div className="sidebar-footer">
          <span>{loadStatus}</span>
        </div>
      ) : null}
    </aside>
  );
}
