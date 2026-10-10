import { useEffect, useState } from 'react';
import type { IntegrationOverview } from '../domain/integration';
import { integrationDataSource } from '../services/integrationService';
import { NotConnectedError } from '../services/retainIQService';
import { useApp } from '../app/AppContext';
type Result = { status: 'loading' | 'ready' | 'error' | 'unavailable'; data: IntegrationOverview | null; error: string | null };
export function useIntegrationHealth(): Result {
  const { dataMode } = useApp();
  const [result, setResult] = useState<Result>({ status: 'loading', data: null, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setResult({ status: 'loading', data: null, error: null });
    integrationDataSource(dataMode).getOverview(controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ status: 'ready', data, error: null });
    }).catch(cause => {
      if (!controller.signal.aborted) setResult(cause instanceof NotConnectedError
        ? { status: 'unavailable', data: null, error: cause.message }
        : { status: 'error', data: null, error: 'Integration health could not be loaded.' });
    });
    return () => controller.abort();
  }, [dataMode]);
  return result;
}
