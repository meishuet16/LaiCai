import type { Currency } from './currency.ts';
export type { Currency } from './currency.ts';
export type Money = { amount_minor: number; currency: Currency };
export type Horizon = 7 | 14 | 30;
export type Role = 'Manager' | 'CSM' | 'Admin' | 'Viewer';
export type Route = 'PRIORITY_REVIEW' | 'HUMAN_REVIEW' | 'OBSERVE' | 'KNOWN_CANCELLATION' | 'NOT_ELIGIBLE';
export type Reliability = 'sufficient_evidence' | 'limited_evidence' | 'insufficient_evidence';
export type Freshness = 'fresh' | 'partially_stale' | 'stale' | 'unknown';
export type PredictionStatus = 'scored' | 'abstained' | 'known_cancellation' | 'not_eligible';

// Shared frontend contract. Fixture probabilities are synthetic, not trained outputs.
export type PredictionSnapshot = {
  tenant_id: string | null; prediction_id: string; prediction_run_id: string; customer_id: string;
  as_of: string | null; generated_at: string | null; status: PredictionStatus;
  p_churn_7d: number | null; p_churn_14d: number | null; p_churn_30d: number | null;
  feature_version: string | null; model_version: string | null; calibration_version: string | null; label_policy_version: string | null;
  reliability: { status: Reliability; reasons: string[] };
  data_freshness: { status: Freshness; input_data_as_of: string | null; stale_sources: string[] };
  uncertainty: { status: 'not_quantified'; method: 'none'; intervals: null };
  explanations_by_horizon: Record<string, unknown>;
  risk_bands_by_horizon: Partial<Record<Horizon, 'low' | 'medium' | 'high'>> | null;
};
export type AccountRecord = {
  tenant_id: string | null; customer_id: string; name: string | null; segment: string | null; plan: string | null;
  account_created_at: string | null; industry: string | null; region: string | null;
  acquisition_channel: string | null; onboarding_cohort: string | null; subscription_state: string | null;
  tenure_days: number | null;
  mrr: Money | null; owner: string | null;
  case_id: string | null; case_status: string | null; next_step: string | null;
  route: Route; route_reason: string; exposure_proxy: Money | null;
  prediction: PredictionSnapshot | null; evidence_kind: 'demo_fixture' | 'source_backed';
};

export type DataMode = 'connected' | 'demo_fixture';

export function customerLabel(account: Pick<AccountRecord, 'customer_id' | 'name'>): string {
  return account.name?.trim() || account.customer_id || 'Account ID unavailable';
}
