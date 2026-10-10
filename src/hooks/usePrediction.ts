import { useEffect, useState } from 'react';
import type { AccountRecord } from '../domain/customer';
import { retainIQService } from '../services/retainIQService';
type Result = { status: 'loading' | 'ready' | 'error'; account: AccountRecord | null; requestedId: string };
export function usePrediction(predictionId: string): Result {
  const [result, setResult] = useState<Result>({ status: 'loading', account: null, requestedId: predictionId });
  useEffect(() => {
    const controller = new AbortController();
    retainIQService.getPrediction(predictionId, controller.signal).then(account => {
      if (!controller.signal.aborted) setResult({ status: 'ready', account, requestedId: predictionId });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ status: 'error', account: null, requestedId: predictionId });
    });
    return () => controller.abort();
  }, [predictionId]);
  return result.requestedId === predictionId ? result : { status: 'loading', account: null, requestedId: predictionId };
}
