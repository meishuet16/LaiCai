import { useEffect, useState } from 'react';
import type { AccountRecord } from '../domain/customer';
import { useApp } from '../app/AppContext';
import { retainIQService } from '../services/retainIQService';
import { matchesCurrencyFilter } from '../domain/customerFilters';

type Result = { status: 'loading' | 'ready' | 'error'; rows: AccountRecord[]; error: string | null };
export function useCustomers(): Result {
  const { query, currency } = useApp();
  const [result, setResult] = useState<Result>({ status: 'loading', rows: [], error: null });
  useEffect(() => {
    const controller = new AbortController();
    retainIQService.listAccounts(controller.signal).then(rows => {
      if (!controller.signal.aborted) setResult({ status: 'ready', rows, error: null });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ status: 'error', rows: [], error: 'Accounts could not be loaded.' });
    });
    return () => controller.abort();
  }, []);
  const filtered = result.rows.filter(row =>
    matchesCurrencyFilter(row, currency) &&
    `${row.name} ${row.customer_id}`.toLowerCase().includes(query.toLowerCase())
  );
  return { ...result, rows: filtered };
}
