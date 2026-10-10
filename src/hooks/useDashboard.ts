import { useCallback, useEffect, useState } from 'react';
import type { DashboardSnapshot } from '../services/dashboardService';
import { dashboardService } from '../services/dashboardService';
import { useApp } from '../app/AppContext';
import { NotConnectedError } from '../services/retainIQService';

type DashboardState = { status: 'loading' | 'ready' | 'error' | 'unavailable'; snapshot: DashboardSnapshot | null; error: string | null };
export function useDashboard() {
  const { dataMode } = useApp();
  const [state, setState] = useState<DashboardState>({ status: 'loading', snapshot: null, error: null });
  const refresh = useCallback(async () => {
    try { const snapshot = await dashboardService.getSnapshot(dataMode); setState({ status: 'ready', snapshot, error: null }); }
    catch (cause) { setState(cause instanceof NotConnectedError
      ? { status: 'unavailable', snapshot: null, error: cause.message }
      : { status: 'error', snapshot: null, error: 'Business Overview data could not be loaded.' }); }
  }, [dataMode]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}
