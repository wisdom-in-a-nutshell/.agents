import { useCallback, useEffect, useRef, useState } from 'react';
import type { ControlPlaneData } from './types';

const AUTO_REFRESH_MS = 5 * 60 * 1000;

export interface ControlPlaneState {
  data: ControlPlaneData | null;
  error: Error | null;
  /** Footer status line, mirrors the original dashboard wording. */
  refreshStatus: string;
}

export function useControlPlane(): ControlPlaneState {
  const [data, setData] = useState<ControlPlaneData | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [refreshStatus, setRefreshStatus] = useState('Auto-refresh every 5m');
  const loadingRef = useRef(false);
  const dataRef = useRef<ControlPlaneData | null>(null);

  const load = useCallback(async (background: boolean) => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    if (!background) setRefreshStatus('Updating');
    try {
      const response = await fetch('/api/control-plane', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Dashboard API returned ${response.status}`);
      }
      const json = (await response.json()) as ControlPlaneData;
      dataRef.current = json;
      setData(json);
      setError(null);
      setRefreshStatus('Auto-refresh every 5m');
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      // Background failure with existing data: keep stale data, just flag it.
      if (dataRef.current && background) {
        setRefreshStatus('Auto-refresh failed');
      } else {
        setError(e);
        setRefreshStatus('Auto-refresh failed');
      }
    } finally {
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    void load(false);
    const id = window.setInterval(() => void load(true), AUTO_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [load]);

  return { data, error, refreshStatus };
}
