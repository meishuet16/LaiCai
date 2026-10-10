import type { AccountRecord, Currency } from './customer.ts';

export function matchesCurrencyFilter(account: AccountRecord, currency: Currency | 'All'): boolean {
  // Unknown-currency accounts stay visible so missing MRR is not hidden by a currency view.
  return currency === 'All' || account.mrr == null || account.mrr.currency === currency;
}
