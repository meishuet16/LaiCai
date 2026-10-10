import { useCallback, useEffect, useState } from 'react';
import type { Capacity, DecisionCase } from '../domain/decision';
import { decisionService } from '../services/decisionService';

type ListState = { status: 'loading' | 'ready' | 'error'; cases: DecisionCase[]; capacity: Capacity | null; error: string | null };
export function useDecisionCases() {
  const [state, setState] = useState<ListState>({ status: 'loading', cases: [], capacity: null, error: null });
  const refresh = useCallback(async () => {
    try { const [cases, capacity] = await Promise.all([decisionService.listCases(), decisionService.getCapacity()]); setState({ status: 'ready', cases, capacity, error: null }); }
    catch { setState({ status: 'error', cases: [], capacity: null, error: 'Decision cases could not be loaded.' }); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}

type DetailState = { status: 'loading' | 'ready' | 'error'; item: DecisionCase | null; error: string | null };
export function useDecisionCase(id: string) {
  const [state, setState] = useState<DetailState>({ status: 'loading', item: null, error: null });
  const refresh = useCallback(async () => {
    try { const item = await decisionService.getCase(id); setState({ status: 'ready', item, error: null }); }
    catch { setState({ status: 'error', item: null, error: 'Case could not be loaded.' }); }
  }, [id]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}
