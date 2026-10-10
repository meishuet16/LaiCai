import { useEffect, useState } from 'react';
import type { TimelineRecord } from '../domain/timeline';
import { timelineService } from '../services/timelineService';

type State = { status: 'loading' | 'ready' | 'error'; record: TimelineRecord | null; error: string | null };
export function useTimeline(customerId: string): State {
  const [state, setState] = useState<State>({ status: 'loading', record: null, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading', record: null, error: null });
    timelineService.getTimeline(customerId, controller.signal).then(record => { if (!controller.signal.aborted) setState({ status: 'ready', record, error: null }); })
      .catch(() => { if (!controller.signal.aborted) setState({ status: 'error', record: null, error: 'Timeline could not be loaded.' }); });
    return () => controller.abort();
  }, [customerId]);
  return state;
}
