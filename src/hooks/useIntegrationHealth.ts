import { useEffect, useState } from 'react';
import type { IntegrationOverview } from '../domain/integration';
import { integrationService } from '../services/integrationService';
type Result = { status: 'loading' | 'ready' | 'error'; data: IntegrationOverview | null };
export function useIntegrationHealth(): Result {
  const [result, setResult] = useState<Result>({ status: 'loading', data: null });
  useEffect(() => {
    const controller = new AbortController();
    integrationService.getOverview(controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ status: 'ready', data });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ status: 'error', data: null });
    });
    return () => controller.abort();
  }, []);
  return result;
}
