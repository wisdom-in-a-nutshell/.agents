import { useCallback, useEffect, useState } from 'react';
import { useControlPlane } from './api';
import { BoardSection } from './components/BoardSection';
import { CatalogExplorer } from './components/CatalogExplorer';
import { OverviewSection } from './components/OverviewSection';
import { RepoExplorer } from './components/RepoExplorer';
import { Sidebar } from './components/Sidebar';
import { NavProvider } from './primitives';
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
];

function initialSection(): SectionId {
  const requested = new URLSearchParams(window.location.search).get('section');
  return SECTIONS.includes(requested as SectionId) ? (requested as SectionId) : 'overview';
}

export function App() {
  const { data, error, loadStatus } = useControlPlane();
  const [section, setSection] = useState<SectionId>(initialSection);
  const [focusedRepoKey, setFocusedRepoKey] = useState('');
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === 'true');

  // Persist + reflect sidebar collapse on <body> (CSS keys off it).
  useEffect(() => {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
  }, [collapsed]);

  const selectSection = useCallback((next: SectionId) => {
    setSection(next);
    setFocusedRepoKey('');
    const url = next === 'overview' ? window.location.pathname : `?section=${next}`;
    window.history.replaceState(null, '', url);
  }, []);

  const navigateToRepo = useCallback((name: string) => {
    setSection('repos');
    setFocusedRepoKey(repoKey(name));
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
              <RepoExplorer data={data} initialRepoKey={focusedRepoKey} />
            </section>
          ) : section === 'skills' || section === 'plugins' || section === 'mcp' || section === 'hooks' ? (
            <section className="content-region content-region-flush" aria-live="polite">
              <NavProvider value={navigateToRepo}>
                <CatalogExplorer data={data} kind={section} />
              </NavProvider>
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
