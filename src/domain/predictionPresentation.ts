import type { AccountRecord, Horizon, PredictionSnapshot } from './customer.ts';

export type PredictionWarning = 'missing_horizon_probability' | 'probability_out_of_range' | 'horizon_order_violation';

export function probabilityAt(prediction: PredictionSnapshot | null, horizon: Horizon): number | null {
  if (!prediction || prediction.status !== 'scored') return null;
  return horizon === 7 ? prediction.p_churn_7d : horizon === 14 ? prediction.p_churn_14d : prediction.p_churn_30d;
}

export function predictionWarnings(prediction: PredictionSnapshot | null): PredictionWarning[] {
  if (!prediction || prediction.status !== 'scored') return [];
  const values = [prediction.p_churn_7d, prediction.p_churn_14d, prediction.p_churn_30d];
  const warnings: PredictionWarning[] = [];
  if (values.some(value => value == null)) warnings.push('missing_horizon_probability');
  if (values.some(value => value != null && (value < 0 || value > 1))) warnings.push('probability_out_of_range');
  const [p7, p14, p30] = values;
  if (p7 != null && p14 != null && p30 != null && (p7 > p14 || p14 > p30)) warnings.push('horizon_order_violation');
  return warnings;
}

export function isNonForecastAccount(account: AccountRecord): boolean {
  return account.route === 'KNOWN_CANCELLATION' || account.route === 'NOT_ELIGIBLE' ||
    account.prediction?.status === 'known_cancellation' || account.prediction?.status === 'not_eligible';
}
