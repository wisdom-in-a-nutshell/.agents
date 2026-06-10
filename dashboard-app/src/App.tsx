import { useCallback, useEffect, useState } from 'react';
import { useControlPlane } from './api';
import { BoardSection } from './components/BoardSection';
import { CatalogExplorer } from './components/CatalogExplorer';
import { GlobalConfigSection } from './components/GlobalConfigSection';
import { OverviewSection } from './components/OverviewSection';
import { RepoExplorer } from './components/RepoExplorer';
import { Sidebar } from './components/Sidebar';
import { NavItemProvider, NavProvider } from './primitives';
import { repoKey } from './selectors';
import { SectionView } from './sections';
import type { SectionId } from './types';

const SIDEBAR_KEY = 'agentControlSidebarCollapsed';
const SECTIONS: SectionId[] = [
  'overview',
  'board',
  'repos',
  'attention',
  'skills',
  'plugins',
  'mcp',
  'hooks',
  'codex',
  'claude',
];

function initialSection(): SectionId {
  const requested = new URLSearchParams(window.location.search).get('section');
  return SECTIONS.includes(requested as SectionId) ? (requested as SectionId) : 'overview';
}

export function App() {
  const { data, error, loadStatus } = useControlPlane();
  const [section, setSection] = useState<SectionId>(initialSection);
  const [focusedRepoKey, setFocusedRepoKey] = useState('');
  const [focusedItem, setFocusedItem] = useState<{ section: SectionId; name: string } | null>(null);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === 'true');

  // Persist + reflect sidebar collapse on <body> (CSS keys off it).
  useEffect(() => {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
  }, [collapsed]);

  const selectSection = useCallback((next: SectionId) => {
    setSection(next);
    setFocusedRepoKey('');
    setFocusedItem(null);
    const url = next === 'overview' ? window.location.pathname : `?section=${next}`;
    window.history.replaceState(null, '', url);
  }, []);

  const navigateToRepo = useCallback((name: string) => {
    setSection('repos');
    setFocusedRepoKey(repoKey(name));
    setFocusedItem(null);
  }, []);

  const navigateToItem = useCallback((next: SectionId, name: string) => {
    setSection(next);
    setFocusedItem({ section: next, name });
    window.history.replaceState(null, '', `?section=${next}`);
  }, []);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(SIDEBAR_KEY, String(next));
      return next;
    });
  }, []);

  return (
    <div className="app-shell">
      <Sidebar
        data={data}
        section={section}
        collapsed={collapsed}
        loadStatus={loadStatus}
        onSelect={selectSection}
        onToggleCollapse={toggleCollapse}
      />
      <main className="main-panel">
        {data ? (
          section === 'overview' ? (
            <section className="content-region" aria-live="polite">
              <NavProvider value={navigateToRepo}>
                <OverviewSection data={data} onNavigate={selectSection} />
              </NavProvider>
            </section>
          ) : section === 'board' ? (
            <section className="content-region" aria-live="polite">
              <NavProvider value={navigateToRepo}>
                <BoardSection data={data} />
              </NavProvider>
            </section>
          ) : section === 'repos' ? (
            <section className="content-region content-region-flush" aria-live="polite">
              <NavItemProvider value={navigateToItem}>
                <RepoExplorer data={data} initialRepoKey={focusedRepoKey} />
              </NavItemProvider>
            </section>
          ) : section === 'skills' || section === 'plugins' || section === 'mcp' || section === 'hooks' ? (
            <section className="content-region content-region-flush" aria-live="polite">
              <NavProvider value={navigateToRepo}>
                <CatalogExplorer
                  data={data}
                  kind={section}
                  focusName={focusedItem && focusedItem.section === section ? focusedItem.name : undefined}
                />
              </NavProvider>
            </section>
          ) : section === 'codex' || section === 'claude' ? (
            <section className="content-region content-region-flush" aria-live="polite">
              <GlobalConfigSection data={data} runtime={section} />
            </section>
          ) : (
            <section className="content-region content-region-flush" aria-live="polite">
              <NavProvider value={navigateToRepo}>
                <div className="cat-head">
                  <h2>Attention</h2>
                  <span className="cat-hint">disabled, dormant, unassigned, and unscoped items</span>
                </div>
                <SectionView section={section} data={data} filter="all" />
              </NavProvider>
            </section>
          )
        ) : (
          <>
            <header className="topbar">
              <div className="section-title">
                <p className="eyebrow">Control Plane</p>
                <h2>Control-plane status</h2>
              </div>
              <div className="topbar-meta">
                <span className={`topbar-pill${error ? ' warning' : ''}`}>
                  <span>Status</span>
                  <strong>{error ? 'Offline' : 'Loading'}</strong>
                </span>
              </div>
            </header>
            <section className="content-region">
              <div className="empty-state">
                <p>{error ? error.message : 'Loading control-plane data…'}</p>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
