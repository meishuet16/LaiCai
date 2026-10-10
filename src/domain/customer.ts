export type Currency = 'MYR' | 'SGD';
export type Money = { amount_minor: number; currency: Currency };
export type Horizon = 7 | 14 | 30;
export type Role = 'Manager' | 'CSM' | 'Admin' | 'Viewer';
export type Route = 'PRIORITY_REVIEW' | 'HUMAN_REVIEW' | 'OBSERVE' | 'KNOWN_CANCELLATION' | 'NOT_ELIGIBLE';
export type Reliability = 'sufficient_evidence' | 'limited_evidence' | 'insufficient_evidence';
export type Freshness = 'fresh' | 'partially_stale' | 'stale' | 'unknown';
export type PredictionStatus = 'scored' | 'abstained' | 'known_cancellation' | 'not_eligible';

// Shared frontend contract. Fixture probabilities are synthetic, not trained outputs.
export type PredictionSnapshot = {
  tenant_id: string; prediction_id: string; prediction_run_id: string; customer_id: string;
  as_of: string; generated_at: string; status: PredictionStatus;
  p_churn_7d: number | null; p_churn_14d: number | null; p_churn_30d: number | null;
  feature_version: string; model_version: string; calibration_version: string; label_policy_version: string;
  reliability: { status: Reliability; reasons: string[] };
  data_freshness: { status: Freshness; input_data_as_of: string | null; stale_sources: string[] };
  uncertainty: { status: 'not_quantified'; method: 'none'; intervals: null };
  explanations_by_horizon: Record<string, unknown>;
};
export type AccountRecord = {
  customer_id: string; name: string; segment: string; plan: string;
  mrr: Money | null; owner: string | null;
  case_id: string | null; case_status: string | null; next_step: string | null;
  route: Route; route_reason: string; exposure_proxy: Money | null;
  prediction: PredictionSnapshot | null; evidence_kind: 'synthetic' | 'source_backed';
};
