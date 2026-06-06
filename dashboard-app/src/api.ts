import { useCallback, useEffect, useRef, useState } from 'react';
import type { ControlPlaneData } from './types';

export interface ControlPlaneState {
  data: ControlPlaneData | null;
  error: Error | null;
  /** Footer status line. Empty when fresh; set only while loading or on failure. */
  loadStatus: string;
}

export function useControlPlane(): ControlPlaneState {
  const [data, setData] = useState<ControlPlaneData | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loadStatus, setLoadStatus] = useState('');
  const loadingRef = useRef(false);

  const load = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoadStatus('Loading…');
    try {
      const response = await fetch('/api/control-plane', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Dashboard API returned ${response.status}`);
      }
      const json = (await response.json()) as ControlPlaneData;
      setData(json);
      setError(null);
      setLoadStatus('');
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      setLoadStatus('Load failed');
    } finally {
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    // The server reads the registries fresh on every request, so a single load
    // renders current data. No background refresh — reopen or reload to refetch.
    void load();
  }, [load]);

  return { data, error, loadStatus };
}
