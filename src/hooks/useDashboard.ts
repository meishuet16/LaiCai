import { useCallback, useEffect, useState } from 'react';
import type { DashboardSnapshot } from '../services/dashboardService';
import { dashboardService } from '../services/dashboardService';

type DashboardState = { status: 'loading' | 'ready' | 'error'; snapshot: DashboardSnapshot | null; error: string | null };
export function useDashboard() {
  const [state, setState] = useState<DashboardState>({ status: 'loading', snapshot: null, error: null });
  const refresh = useCallback(async () => {
    try { const snapshot = await dashboardService.getSnapshot(); setState({ status: 'ready', snapshot, error: null }); }
    catch { setState({ status: 'error', snapshot: null, error: 'Business Overview data could not be loaded.' }); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}
