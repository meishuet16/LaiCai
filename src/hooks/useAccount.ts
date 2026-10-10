import { useEffect, useState } from 'react';
import type { AccountRecord } from '../domain/customer';
import { accountDataSource, NotConnectedError } from '../services/retainIQService';
import { useApp } from '../app/AppContext';
type Result = { status: 'loading' | 'ready' | 'error' | 'unavailable'; account: AccountRecord | null; error: string | null };
export function useAccount(customerId: string): Result {
  const { dataMode } = useApp();
  const [result, setResult] = useState<Result>({ status: 'loading', account: null, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setResult({ status: 'loading', account: null, error: null });
    accountDataSource(dataMode).getAccount(customerId, controller.signal).then(account => {
      if (!controller.signal.aborted) setResult({ status: 'ready', account, error: null });
    }).catch(cause => {
      if (!controller.signal.aborted) setResult(cause instanceof NotConnectedError
        ? { status: 'unavailable', account: null, error: cause.message }
        : { status: 'error', account: null, error: 'Customer profile could not be loaded.' });
    });
    return () => controller.abort();
  }, [customerId, dataMode]);
  return result;
}
