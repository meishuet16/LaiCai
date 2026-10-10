import { useEffect, useState } from 'react';
import type { AccountRecord } from '../domain/customer';
import { accountDataSource, NotConnectedError } from '../services/retainIQService';
import { useApp } from '../app/AppContext';
type Result = { status: 'loading' | 'ready' | 'error' | 'unavailable'; account: AccountRecord | null; requestedId: string; error: string | null };
export function usePrediction(predictionId: string): Result {
  const { dataMode } = useApp();
  const [result, setResult] = useState<Result>({ status: 'loading', account: null, requestedId: predictionId, error: null });
  useEffect(() => {
    const controller = new AbortController();
    accountDataSource(dataMode).getPrediction(predictionId, controller.signal).then(account => {
      if (!controller.signal.aborted) setResult({ status: 'ready', account, requestedId: predictionId, error: null });
    }).catch(cause => {
      if (!controller.signal.aborted) setResult(cause instanceof NotConnectedError
        ? { status: 'unavailable', account: null, requestedId: predictionId, error: cause.message }
        : { status: 'error', account: null, requestedId: predictionId, error: 'Prediction could not be loaded.' });
    });
    return () => controller.abort();
  }, [predictionId, dataMode]);
  return result.requestedId === predictionId ? result : { status: 'loading', account: null, requestedId: predictionId, error: null };
}
