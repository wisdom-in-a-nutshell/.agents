import { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { useControlPlane } from './api';
import { BoardSection } from './components/BoardSection';
import { CatalogExplorer } from './components/CatalogExplorer';
import { FilterBar, MetricsGrid, Topbar, WarningsPanel } from './components/Chrome';
import { RepoExplorer } from './components/RepoExplorer';
import { Sidebar } from './components/Sidebar';
import { NavProvider } from './primitives';
import { countForFilter, formatDate, repoDisplayName, repoKey } from './selectors';
import { SectionView } from './sections';
import type { SectionId } from './types';

const SIDEBAR_KEY = 'agentControlSidebarCollapsed';
const SECTIONS: SectionId[] = ['board', 'repos', 'attention', 'skills', 'plugins', 'mcp', 'hooks'];

function initialSection(): SectionId {
  const requested = new URLSearchParams(window.location.search).get('section');
  return SECTIONS.includes(requested as SectionId) ? (requested as SectionId) : 'board';
}

export function App() {
  const { data, error, refreshStatus } = useControlPlane();
  const [section, setSection] = useState<SectionId>(initialSection);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [focusedRepoKey, setFocusedRepoKey] = useState('');
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_KEY) === 'true',
  );

  // Persist + reflect sidebar collapse on <body> (CSS keys off it).
  useEffect(() => {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
  }, [collapsed]);

  const selectSection = useCallback((next: SectionId) => {
    setSection(next);
    setFilter('all');
    setFocusedRepoKey('');
    const url = next === 'board' ? window.location.pathname : `?section=${next}`;
    window.history.replaceState(null, '', url);
  }, []);

  const navigateToRepo = useCallback((name: string) => {
    setSection('repos');
    setFilter('all');
    setFocusedRepoKey(repoKey(name));
    setQuery(repoDisplayName(name));
  }, []);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(SIDEBAR_KEY, String(next));
      return next;
    });
  }, []);

  // Drop a filter that no longer matches anything (mirrors original normalize).
  useEffect(() => {
    if (data && filter !== 'all' && countForFilter(data, section, filter) === 0) {
      setFilter('all');
    }
  }, [data, section, filter]);

  // Smooth-scroll + focus the targeted repo card after it renders.
  useLayoutEffect(() => {
    if (!data || section !== 'repos' || !focusedRepoKey) return;
    const card = document.querySelector<HTMLElement>(`[data-repo-key="${focusedRepoKey}"]`);
    if (!card) return;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.focus({ preventScroll: true });
  }, [data, section, focusedRepoKey]);

  const lastUpdated = data ? `Updated ${formatDate(data.generated_at_utc)}` : 'Not loaded';

  return (
    <div className="app-shell">
      <Sidebar
        data={data}
        section={section}
        collapsed={collapsed}
        query={query}
        lastUpdated={lastUpdated}
        refreshStatus={refreshStatus}
        onSelect={selectSection}
        onToggleCollapse={toggleCollapse}
        onQueryChange={setQuery}
      />
      <main className="main-panel">
        {data ? (
          section === 'board' ? (
            <section className="content-region" aria-live="polite">
              <NavProvider value={navigateToRepo}>
                <BoardSection data={data} />
              </NavProvider>
            </section>
          ) : section === 'repos' ? (
            <section className="content-region content-region-flush" aria-live="polite">
              <RepoExplorer data={data} query={query} initialRepoKey={focusedRepoKey} />
            </section>
          ) : section === 'skills' || section === 'plugins' || section === 'mcp' || section === 'hooks' ? (
            <section className="content-region content-region-flush" aria-live="polite">
              <NavProvider value={navigateToRepo}>
                <CatalogExplorer data={data} kind={section} query={query} />
              </NavProvider>
            </section>
          ) : (
            <>
              <Topbar data={data} section={section} />
              <MetricsGrid data={data} section={section} />
              <WarningsPanel data={data} section={section} />
              <FilterBar data={data} section={section} filter={filter} onSelect={setFilter} />
              <section className="content-region" aria-live="polite">
                <NavProvider value={navigateToRepo}>
                  <SectionView
                    section={section}
                    data={data}
                    filter={filter}
                    query={query}
                    focusedRepoKey={focusedRepoKey}
                  />
                </NavProvider>
              </section>
            </>
          )
        ) : (
          <>
            <header className="topbar">
              <div className="section-title">
                <p className="eyebrow">Overview</p>
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
