import { useCallback, useEffect, useRef, useState } from 'react';
import type { ControlPlaneData } from './types';

export interface ControlPlaneState {
  data: ControlPlaneData | null;
  error: Error | null;
  /** Footer status line. Empty when fresh; set only while loading or on failure. */
  refreshStatus: string;
}

export function useControlPlane(): ControlPlaneState {
  const [data, setData] = useState<ControlPlaneData | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [refreshStatus, setRefreshStatus] = useState('');
  const loadingRef = useRef(false);
  const dataRef = useRef<ControlPlaneData | null>(null);

  const load = useCallback(async (background: boolean) => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    if (!background) setRefreshStatus('Loading…');
    try {
      const response = await fetch('/api/control-plane', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Dashboard API returned ${response.status}`);
      }
      const json = (await response.json()) as ControlPlaneData;
      dataRef.current = json;
      setData(json);
      setError(null);
      setRefreshStatus('');
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      // Background failure with existing data: keep stale data, just flag it.
      if (dataRef.current && background) {
        setRefreshStatus('Refresh failed');
      } else {
        setError(e);
        setRefreshStatus('Refresh failed');
      }
    } finally {
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    // The server reads the registries fresh on every request, so a single load
    // renders current data. No background refresh — reopen or reload to refetch.
    void load(false);
  }, [load]);

  return { data, error, refreshStatus };
}
