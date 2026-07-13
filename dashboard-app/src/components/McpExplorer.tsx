import { useEffect, useMemo, useState } from 'react';
import { useNavigateRepo } from '../primitives';
import { cleanArray, repoDisplayName, sourceHref } from '../selectors';
import type { ControlPlaneData, Item } from '../types';

const CLIENT_LABELS: Record<string, { label: string; surface: string }> = {
  codex: { label: 'Codex', surface: '.codex/config.toml' },
  claude: { label: 'Claude', surface: '.mcp.json' },
  copilot: { label: 'Copilot', surface: 'user + workspace MCP' },
};

function clientsForRepo(item: Item, repoName: string): string[] {
  const matrix = item.details.repo_clients;
  return matrix && typeof matrix === 'object' ? cleanArray(matrix[repoName]) : [];
}

function endpoint(item: Item): string {
  if (item.details.url) return String(item.details.url);
  if (item.details.command) return String(item.details.command);
  return 'No endpoint configured';
}

export function McpExplorer({
  data,
  focusName,
}: {
  data: ControlPlaneData;
  focusName?: string;
}) {
  const navigateRepo = useNavigateRepo();
  const clients = (data.runtimes ?? ['codex', 'claude', 'copilot']).filter(
    (client) => CLIENT_LABELS[client],
  );
  const items = useMemo(
    () => data.groups.mcp.slice().sort((a, b) => a.name.localeCompare(b.name)),
    [data.groups.mcp],
  );
  const repos = useMemo(
    () => data.groups.repos.slice().sort((a, b) => a.name.localeCompare(b.name)),
    [data.groups.repos],
  );
  const [selectedName, setSelectedName] = useState(focusName ?? '');

  useEffect(() => {
    if (focusName) setSelectedName(focusName);
  }, [focusName]);

  const selected = items.find((item) => item.name === selectedName);
  const visibleItems = selected ? [selected] : items;
  const assignedCellCount = repos.reduce(
    (total, repo) =>
      total +
      clients.filter((client) =>
        visibleItems.some((item) => clientsForRepo(item, repo.name).includes(client)),
      ).length,
    0,
  );

  return (
    <div className="mcp-view">
      <header className="mcp-head">
        <div>
          <h2>MCP distribution</h2>
          <p>Repository coverage runs down the page; client delivery runs across it.</p>
        </div>
        <dl className="mcp-summary" aria-label="MCP matrix summary">
          <div>
            <dt>Servers</dt>
            <dd>{items.length}</dd>
          </div>
          <div>
            <dt>Clients</dt>
            <dd>{clients.length}</dd>
          </div>
          <div>
            <dt>Active cells</dt>
            <dd>{assignedCellCount}</dd>
          </div>
        </dl>
      </header>

      <nav className="mcp-filters" aria-label="Filter matrix by MCP server">
        <button
          type="button"
          className={!selected ? 'active' : undefined}
          aria-pressed={!selected}
          onClick={() => setSelectedName('')}
        >
          All servers <strong>{items.length}</strong>
        </button>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={selected?.name === item.name ? 'active' : undefined}
            aria-pressed={selected?.name === item.name}
            onClick={() => setSelectedName(selected?.name === item.name ? '' : item.name)}
          >
            {item.name}
            <strong>{item.repos.length}</strong>
          </button>
        ))}
      </nav>

      <div className="mcp-definition" aria-live="polite">
        {selected ? (
          <>
            <div className="mcp-definition-main">
              <strong>{selected.name}</strong>
              <code>{endpoint(selected)}</code>
            </div>
            <div className="mcp-definition-meta">
              <span>{cleanArray(selected.details.clients).join(' · ') || 'unassigned'}</span>
              {cleanArray(selected.details.global_clients).length ? (
                <span>Global: {cleanArray(selected.details.global_clients).join(' · ')}</span>
              ) : null}
              <span>{selected.repos.length} repos</span>
              <a href={sourceHref(selected)} target="_blank" rel="noreferrer">
                Registry
              </a>
            </div>
          </>
        ) : (
          <p>Select a server to isolate its coverage and inspect its endpoint.</p>
        )}
      </div>

      <div className="mcp-matrix-scroll">
        <table className="mcp-matrix">
          <caption className="visually-hidden">
            MCP servers available to each agent client in each managed repository
          </caption>
          <thead>
            <tr>
              <th scope="col">Repository</th>
              {clients.map((client) => (
                <th scope="col" key={client}>
                  <span>{CLIENT_LABELS[client].label}</span>
                  <code>{CLIENT_LABELS[client].surface}</code>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {repos.map((repo) => (
              <tr key={repo.id}>
                <th scope="row">
                  <button type="button" onClick={() => navigateRepo(repo.name)}>
                    {repoDisplayName(repo.name)}
                  </button>
                </th>
                {clients.map((client) => {
                  const cellItems = visibleItems.filter((item) =>
                    clientsForRepo(item, repo.name).includes(client),
                  );
                  return (
                    <td key={client} className={cellItems.length ? 'has-target' : undefined}>
                      {cellItems.length ? (
                        <div className="mcp-cell-items">
                          {cellItems.map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              className={selected?.name === item.name ? 'active' : undefined}
                              onClick={() => setSelectedName(item.name)}
                            >
                              {item.name}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="mcp-cell-empty" aria-label="No MCP servers">
                          —
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
