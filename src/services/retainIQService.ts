import type { AccountRecord, Currency, Freshness, Money, PredictionSnapshot, PredictionStatus, Reliability, Route } from '../domain/customer';

export interface RetainIQDataSource {
  listAccounts(signal?: AbortSignal): Promise<AccountRecord[]>;
  getAccount(customerId: string, signal?: AbortSignal): Promise<AccountRecord | null>;
  getPrediction(predictionId: string, signal?: AbortSignal): Promise<AccountRecord | null>;
}

type Fixture = { id: string; name: string; segment: string; plan: string; mrr: number | null; currency: Currency; owner: string | null; route: Route; risk: [number, number, number] | null; predictionStatus?: PredictionStatus; reliability: Reliability; freshness: Freshness; status: string; next: string; reason: string };
const sourceRows: Fixture[] = [
  { id: 'c01', name: 'Northwind Logistics', segment: 'Enterprise', plan: 'Growth, annual', mrr: 120000, currency: 'MYR', owner: 'Janice', route: 'PRIORITY_REVIEW', risk: [.2, .33, .52], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Assigned', next: 'Execute action', reason: '2 failed payments in 30 days' },
  { id: 'c02', name: 'Kopi Ventures', segment: 'SMB', plan: 'Starter, monthly', mrr: 10000, currency: 'MYR', owner: null, route: 'PRIORITY_REVIEW', risk: [.3, .45, .7], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Proposed', next: 'Approve or modify', reason: 'Usage down 62% vs its own baseline' },
  { id: 'c03', name: 'Meridian Foods', segment: 'Mid-market', plan: 'Growth, monthly', mrr: 50000, currency: 'MYR', owner: 'Jasmine', route: 'PRIORITY_REVIEW', risk: [.4, .55, .72], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Follow-up due', next: 'Record follow-up', reason: 'No sessions for 11 days' },
  { id: 'c04', name: 'Atlas Retail', segment: 'Mid-market', plan: 'Growth, monthly', mrr: 90000, currency: 'MYR', owner: null, route: 'HUMAN_REVIEW', risk: [.1, .2, .3], reliability: 'limited_evidence', freshness: 'partially_stale', status: 'Proposed', next: 'Verify source data', reason: 'Only 9 days of history; billing source is stale' },
  { id: 'c08', name: 'Lumen Education', segment: 'Enterprise', plan: 'Scale, annual', mrr: 240000, currency: 'SGD', owner: null, route: 'PRIORITY_REVIEW', risk: [.2, .32, .5], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Human reviewed', next: 'Assign owner', reason: 'Usage down 41% vs its own baseline' },
  { id: 'c06', name: 'Bayu Fitness', segment: 'SMB', plan: 'Starter, monthly', mrr: 25000, currency: 'MYR', owner: null, route: 'KNOWN_CANCELLATION', risk: null, predictionStatus: 'known_cancellation', reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Cancellation recovery', next: 'Cancellation workflow', reason: 'Cancellation request was known at cutoff' },
  { id: 'c07', name: 'Helios Clinics', segment: 'SMB', plan: 'Unknown', mrr: null, currency: 'MYR', owner: null, route: 'HUMAN_REVIEW', risk: null, predictionStatus: 'abstained', reliability: 'insufficient_evidence', freshness: 'unknown', status: 'Proposed', next: 'Verify source data', reason: 'Identity conflict and missing MRR' },
  { id: 'c05', name: 'Orchid Studios', segment: 'SMB', plan: 'Starter, monthly', mrr: 18000, currency: 'MYR', owner: 'Janice', route: 'OBSERVE', risk: [.04, .08, .14], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Observe', next: 'Monitor', reason: 'Current risk does not justify a review slot' },
  { id: 'c09', name: 'Pinecrest Labs', segment: 'SMB', plan: 'Trial', mrr: null, currency: 'SGD', owner: null, route: 'NOT_ELIGIBLE', risk: null, predictionStatus: 'not_eligible', reliability: 'insufficient_evidence', freshness: 'unknown', status: 'Not eligible', next: 'No action', reason: 'No active paid subscription at cutoff' },
];

const asOf = '2026-10-10T00:00:00Z';
function toRecord(row: Fixture): AccountRecord {
  const prediction: PredictionSnapshot = {
    tenant_id: 'tenant_abc', prediction_id: `demo_pred_${row.id}`, prediction_run_id: 'demo_run_20261010', customer_id: row.id,
    as_of: asOf, generated_at: '2026-10-10T00:00:10Z', status: row.predictionStatus ?? 'scored',
    p_churn_7d: row.risk?.[0] ?? null, p_churn_14d: row.risk?.[1] ?? null, p_churn_30d: row.risk?.[2] ?? null,
    feature_version: 'demo_features_v1', model_version: 'demo_model_v1', calibration_version: 'demo_calibration_v1', label_policy_version: 'demo_churn_policy_v1',
    reliability: { status: row.reliability, reasons: [] },
    data_freshness: { status: row.freshness, input_data_as_of: asOf, stale_sources: row.freshness === 'fresh' ? [] : ['billing'] },
    uncertainty: { status: 'not_quantified', method: 'none', intervals: null }, explanations_by_horizon: {},
  };
  const mrr: Money | null = row.mrr == null ? null : { amount_minor: row.mrr, currency: row.currency };
  return { customer_id: row.id, name: row.name, segment: row.segment, plan: row.plan,
    mrr, owner: row.owner, case_id: `demo_case_${row.id}`, case_status: row.status, next_step: row.next,
    route: row.route, route_reason: row.reason,
    exposure_proxy: row.mrr != null && row.risk && row.route === 'PRIORITY_REVIEW' && row.freshness === 'fresh' && row.reliability === 'sufficient_evidence'
      ? { amount_minor: Math.round(row.mrr * row.risk[2]), currency: row.currency } : null,
    prediction, evidence_kind: 'synthetic' };
}

const fixtureAccounts = sourceRows.map(toRecord);
export const fixtureDataSource: RetainIQDataSource = {
  async listAccounts(signal) { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return fixtureAccounts; },
  async getAccount(customerId, signal) { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return fixtureAccounts.find(row => row.customer_id === customerId) ?? null; },
  async getPrediction(predictionId, signal) { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return fixtureAccounts.find(row => row.prediction?.prediction_id === predictionId) ?? null; },
};

// Stage 1 has no backend connection. Later API adapters implement this interface.
export const retainIQService: RetainIQDataSource = fixtureDataSource;
