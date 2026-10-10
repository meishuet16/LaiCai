import { useEffect, useState } from 'react';
import type { AccountRecord } from '../domain/customer';
import { retainIQService } from '../services/retainIQService';
type Result = { status: 'loading' | 'ready' | 'error'; account: AccountRecord | null };
export function useAccount(customerId: string): Result {
  const [result, setResult] = useState<Result>({ status: 'loading', account: null });
  useEffect(() => {
    const controller = new AbortController();
    retainIQService.getAccount(customerId, controller.signal).then(account => {
      if (!controller.signal.aborted) setResult({ status: 'ready', account });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ status: 'error', account: null });
    });
    return () => controller.abort();
  }, [customerId]);
  return result;
}
