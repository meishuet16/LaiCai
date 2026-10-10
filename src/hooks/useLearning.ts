import { useEffect, useState } from 'react';
import { getBackendLearning, type LearningOverview } from '../services/backendClient.ts';

type LearningState = { status: 'loading' | 'ready' | 'error'; data: LearningOverview | null; error: string | null };

export function useLearning() {
  const [state, setState] = useState<LearningState>({ status: 'loading', data: null, error: null });
  useEffect(() => {
    const controller = new AbortController();
    getBackendLearning(controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ status: 'ready', data, error: null }); })
      .catch(cause => { if (!controller.signal.aborted) setState({ status: 'error', data: null, error: cause instanceof Error ? cause.message : 'Learning status could not be loaded.' }); });
    return () => controller.abort();
  }, []);
  return state;
}
