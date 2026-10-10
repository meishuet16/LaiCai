import { useEffect, useState } from 'react';
import type { TimelineRecord } from '../domain/timeline';
import { timelineDataSource } from '../services/timelineService';
import { useApp } from '../app/AppContext';
import { NotConnectedError } from '../services/retainIQService';

type State = { status: 'loading' | 'ready' | 'error' | 'unavailable'; record: TimelineRecord | null; error: string | null };
export function useTimeline(customerId: string): State {
  const { dataMode } = useApp();
  const [state, setState] = useState<State>({ status: 'loading', record: null, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading', record: null, error: null });
    timelineDataSource(dataMode).getTimeline(customerId, controller.signal).then(record => { if (!controller.signal.aborted) setState({ status: 'ready', record, error: null }); })
      .catch(cause => { if (!controller.signal.aborted) setState(cause instanceof NotConnectedError
        ? { status: 'unavailable', record: null, error: cause.message }
        : { status: 'error', record: null, error: 'Timeline could not be loaded.' }); });
    return () => controller.abort();
  }, [customerId, dataMode]);
  return state;
}
