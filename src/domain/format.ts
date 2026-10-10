import type { Horizon, Money, PredictionSnapshot } from './customer';
export function formatMoney(money: Money | null): string {
  if (!money) return 'N/A';
  return new Intl.NumberFormat('en-MY', { style: 'currency', currency: money.currency, maximumFractionDigits: 0 }).format(money.amount_minor / 100);
}
export function formatRisk(prediction: PredictionSnapshot | null, horizon: Horizon): string {
  if (!prediction || prediction.status !== 'scored') return 'N/A';
  const value = horizon === 7 ? prediction.p_churn_7d : horizon === 14 ? prediction.p_churn_14d : prediction.p_churn_30d;
  return value == null ? 'N/A' : `${Math.round(value * 100)}%`;
}
export function formatDateTime(value: string | null): string {
  return value ? new Intl.DateTimeFormat('en-MY', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value)) + ' UTC' : 'N/A';
}
