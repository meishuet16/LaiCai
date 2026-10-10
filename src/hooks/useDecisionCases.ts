import { useCallback, useEffect, useState } from 'react';
import type { Capacity, DecisionCase } from '../domain/decision';
import { decisionService } from '../services/decisionService';
import { useApp } from '../app/AppContext';
import { NotConnectedError } from '../services/retainIQService';

type ListState = { status: 'loading' | 'ready' | 'error' | 'unavailable'; cases: DecisionCase[]; capacity: Capacity | null; error: string | null };
export function useDecisionCases() {
  const { dataMode } = useApp();
  const [state, setState] = useState<ListState>({ status: 'loading', cases: [], capacity: null, error: null });
  const refresh = useCallback(async () => {
    if (dataMode !== 'demo_fixture') { setState({ status: 'unavailable', cases: [], capacity: null, error: 'Decision-case, capacity, and approval APIs are not connected in this frontend.' }); return; }
    try { const [cases, capacity] = await Promise.all([decisionService.listCases(), decisionService.getCapacity()]); setState({ status: 'ready', cases, capacity, error: null }); }
    catch (cause) { setState({ status: 'error', cases: [], capacity: null, error: cause instanceof Error ? cause.message : 'Decision cases could not be loaded.' }); }
  }, [dataMode]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}

type DetailState = { status: 'loading' | 'ready' | 'error' | 'unavailable'; item: DecisionCase | null; error: string | null };
export function useDecisionCase(id: string) {
  const { dataMode } = useApp();
  const [state, setState] = useState<DetailState>({ status: 'loading', item: null, error: null });
  const refresh = useCallback(async () => {
    if (dataMode !== 'demo_fixture') { setState({ status: 'unavailable', item: null, error: 'Decision-case read API is not connected in this frontend.' }); return; }
    try { const item = await decisionService.getCase(id); setState({ status: 'ready', item, error: null }); }
    catch { setState({ status: 'error', item: null, error: 'Case could not be loaded.' }); }
  }, [id, dataMode]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}
