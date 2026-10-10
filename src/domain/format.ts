import type { Horizon, Money, PredictionSnapshot } from './customer.ts';
import { isBackendCurrency } from './currency.ts';
export function currencyFractionDigits(currency: string): number | null {
  if (!isBackendCurrency(currency)) return null;
  try { return new Intl.NumberFormat('en-MY', { style: 'currency', currency }).resolvedOptions().maximumFractionDigits ?? 2; }
  catch { return null; }
}
export function minorToMajor(money: Money | null | undefined, options: { allowNegative?: boolean } = {}): number | null {
  if (!money || !Number.isSafeInteger(money.amount_minor) || !isBackendCurrency(money.currency) || (!options.allowNegative && money.amount_minor < 0)) return null;
  const digits = currencyFractionDigits(money.currency);
  return digits == null ? null : money.amount_minor / (10 ** digits);
}
export function majorToMinor(amount: number, currency: string, options: { allowNegative?: boolean } = {}): number | null {
  const digits = currencyFractionDigits(currency);
  if (digits == null || !Number.isFinite(amount) || (!options.allowNegative && amount < 0)) return null;
  const minor = Math.round(amount * (10 ** digits));
  return Number.isSafeInteger(minor) ? minor : null;
}
export function formatMoney(money: Money | null | undefined, options: { allowNegative?: boolean; locale?: string } = {}): string {
  const majorAmount = minorToMajor(money, options);
  if (majorAmount == null || !money) return 'N/A';
  try {
    const formatter = new Intl.NumberFormat(options.locale ?? 'en-MY', { style: 'currency', currency: money.currency });
    return formatter.format(majorAmount);
  } catch {
    return 'N/A';
  }
}
export function formatRisk(prediction: PredictionSnapshot | null, horizon: Horizon): string {
  if (!prediction || prediction.status !== 'scored') return 'N/A';
  const value = horizon === 7 ? prediction.p_churn_7d : horizon === 14 ? prediction.p_churn_14d : prediction.p_churn_30d;
  return value == null ? 'N/A' : `${Math.round(value * 100)}%`;
}
export function formatDateTime(value: string | null): string {
  if (!value || Number.isNaN(Date.parse(value))) return 'N/A';
  return new Intl.DateTimeFormat('en-MY', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value)) + ' UTC';
}
