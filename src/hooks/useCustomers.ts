import { useEffect, useState } from 'react';
import type { AccountRecord } from '../domain/customer';
import { useApp } from '../app/AppContext';
import { accountDataSource, NotConnectedError } from '../services/retainIQService';
import { matchesCurrencyFilter } from '../domain/customerFilters';

type Result = { status: 'loading' | 'ready' | 'error' | 'unavailable'; rows: AccountRecord[]; error: string | null };
export function useCustomers({ ignoreGlobalFilters = false }: { ignoreGlobalFilters?: boolean } = {}): Result {
  const { query, currency, dataMode } = useApp();
  const [result, setResult] = useState<Result>({ status: 'loading', rows: [], error: null });
  useEffect(() => {
    const controller = new AbortController();
    accountDataSource(dataMode).listAccounts(controller.signal).then(rows => {
      if (!controller.signal.aborted) setResult({ status: 'ready', rows, error: null });
    }).catch(cause => {
      if (!controller.signal.aborted) setResult(cause instanceof NotConnectedError
        ? { status: 'unavailable', rows: [], error: cause.message }
        : { status: 'error', rows: [], error: 'Accounts could not be loaded.' });
    });
    return () => controller.abort();
  }, [dataMode]);
  const filtered = ignoreGlobalFilters ? result.rows : result.rows.filter(row =>
    matchesCurrencyFilter(row, currency) &&
    row.customer_id.toLowerCase().includes(query.toLowerCase())
  );
  return { ...result, rows: filtered };
}
