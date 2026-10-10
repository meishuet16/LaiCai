import { useCallback, useEffect, useState } from 'react';
import type { Capacity, DecisionCase } from '../domain/decision';
import { decisionDataSource } from '../services/decisionService';
import { useApp } from '../app/AppContext';

type ListState = { status: 'loading' | 'ready' | 'error' | 'unavailable'; cases: DecisionCase[]; capacity: Capacity | null; error: string | null };
export function useDecisionCases() {
  const { dataMode } = useApp();
  const [state, setState] = useState<ListState>({ status: 'loading', cases: [], capacity: null, error: null });
  const refresh = useCallback(async () => {
    const service = decisionDataSource(dataMode);
    try { const [cases, capacity] = await Promise.all([service.listCases(), service.getCapacity()]); setState({ status: 'ready', cases, capacity, error: null }); }
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
    try { const item = await decisionDataSource(dataMode).getCase(id); setState({ status: 'ready', item, error: null }); }
    catch { setState({ status: 'error', item: null, error: 'Case could not be loaded.' }); }
  }, [id, dataMode]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}
