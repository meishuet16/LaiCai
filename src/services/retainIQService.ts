import type { AccountRecord, Currency, DataMode, Freshness, Money, PredictionSnapshot, PredictionStatus, Reliability, Route } from '../domain/customer.ts';
import { getBackendDashboardAccounts, routeAccountThroughBackend } from './backendClient.ts';

export interface RetainIQDataSource {
  listAccounts(signal?: AbortSignal): Promise<AccountRecord[]>;
  getAccount(customerId: string, signal?: AbortSignal): Promise<AccountRecord | null>;
  getPrediction(predictionId: string, signal?: AbortSignal): Promise<AccountRecord | null>;
}

type Fixture = { id: string; name: string; segment: string | null; plan: string | null; mrr: number | null; currency: Currency; owner: string | null; route: Route; risk: [number, number, number] | null; predictionStatus?: PredictionStatus; reliability: Reliability; freshness: Freshness; status: string; next: string; reason: string };
const sourceRows: Fixture[] = [
  { id: 'c01', name: 'Northwind Logistics', segment: 'Enterprise', plan: 'Growth, annual', mrr: 120000, currency: 'MYR', owner: 'Janice', route: 'PRIORITY_REVIEW', risk: [.2, .33, .52], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Assigned', next: 'Execute action', reason: 'Sample failed-payment facts; not an entitlement or churn conclusion' },
  { id: 'c02', name: 'Kopi Ventures', segment: 'SMB', plan: 'Starter, monthly', mrr: 10000, currency: 'MYR', owner: null, route: 'PRIORITY_REVIEW', risk: [.3, .45, .7], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Proposed', next: 'Approve or modify', reason: 'Sample usage is below a sample personal baseline' },
  { id: 'c03', name: 'Meridian Foods', segment: 'Mid-market', plan: 'Growth, monthly', mrr: 50000, currency: 'MYR', owner: 'Jasmine', route: 'PRIORITY_REVIEW', risk: [.4, .55, .72], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Follow-up due', next: 'Record follow-up', reason: 'Sample usage inactivity indicator' },
  { id: 'c04', name: 'Atlas Retail', segment: 'Mid-market', plan: 'Growth, monthly', mrr: 90000, currency: 'MYR', owner: null, route: 'HUMAN_REVIEW', risk: [.1, .2, .3], reliability: 'limited_evidence', freshness: 'partially_stale', status: 'Proposed', next: 'Verify source data', reason: 'Sample fixture has short history and stale billing' },
  { id: 'c08', name: 'Lumen Education', segment: 'Enterprise', plan: 'Scale, annual', mrr: 240000, currency: 'SGD', owner: null, route: 'PRIORITY_REVIEW', risk: [.2, .32, .5], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Human reviewed', next: 'Assign owner', reason: 'Sample usage is below a sample personal baseline' },
  { id: 'c06', name: 'Bayu Fitness', segment: 'SMB', plan: 'Starter, monthly', mrr: 25000, currency: 'MYR', owner: null, route: 'KNOWN_CANCELLATION', risk: null, predictionStatus: 'known_cancellation', reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Cancellation workflow', next: 'No forecast', reason: 'Sample cancellation request; not necessarily effective cancellation' },
  { id: 'c07', name: 'Helios Clinics', segment: 'SMB', plan: 'Unknown', mrr: null, currency: 'MYR', owner: null, route: 'HUMAN_REVIEW', risk: null, predictionStatus: 'abstained', reliability: 'insufficient_evidence', freshness: 'unknown', status: 'Proposed', next: 'Verify source data', reason: 'Sample identity conflict and missing MRR' },
  { id: 'c05', name: 'Orchid Studios', segment: 'SMB', plan: 'Starter, monthly', mrr: 18000, currency: 'MYR', owner: 'Janice', route: 'OBSERVE', risk: [.04, .08, .14], reliability: 'sufficient_evidence', freshness: 'fresh', status: 'Observe', next: 'Monitor', reason: 'Sample route is Observe' },
  { id: 'c09', name: 'Pinecrest Labs', segment: 'SMB', plan: 'Trial', mrr: null, currency: 'SGD', owner: null, route: 'NOT_ELIGIBLE', risk: null, predictionStatus: 'not_eligible', reliability: 'insufficient_evidence', freshness: 'unknown', status: 'Not eligible', next: 'No action', reason: 'Sample fixture has no active paid subscription' },
];
function toRecord(row: Fixture): AccountRecord {
  const prediction: PredictionSnapshot = {
    tenant_id: null, prediction_id: `demo_pred_${row.id}`, prediction_run_id: `demo_run_${row.id}`, customer_id: row.id,
    as_of: null, generated_at: null, status: row.predictionStatus ?? 'scored',
    p_churn_7d: row.risk?.[0] ?? null, p_churn_14d: row.risk?.[1] ?? null, p_churn_30d: row.risk?.[2] ?? null,
    feature_version: null, model_version: null, calibration_version: null, label_policy_version: null,
    reliability: { status: row.reliability, reasons: [] },
    data_freshness: { status: row.freshness, input_data_as_of: null, stale_sources: row.freshness === 'fresh' ? [] : ['billing'] },
    uncertainty: { status: 'not_quantified', method: 'none', intervals: null }, explanations_by_horizon: {}, risk_bands_by_horizon: null,
  };
  const mrr: Money | null = row.mrr == null ? null : { amount_minor: row.mrr, currency: row.currency };
  return { tenant_id: null, customer_id: row.id, name: row.name, segment: row.segment, plan: row.plan,
    account_created_at: null, industry: null, region: null, acquisition_channel: null, onboarding_cohort: null, subscription_state: null, tenure_days: null,
    mrr, owner: row.owner, case_id: `demo_case_${row.id}`, case_status: row.status, next_step: row.next,
    route: row.route, route_reason: row.reason,
    exposure_proxy: row.mrr != null && row.risk && row.route === 'PRIORITY_REVIEW' && row.freshness === 'fresh' && row.reliability === 'sufficient_evidence'
      ? { amount_minor: Math.round(row.mrr * row.risk[2]), currency: row.currency } : null,
    prediction, evidence_kind: 'demo_fixture' };
}

const fixtureAccounts = sourceRows.map(toRecord);
export const fixtureDataSource: RetainIQDataSource = {
  async listAccounts(signal) { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return fixtureAccounts; },
  async getAccount(customerId, signal) { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return fixtureAccounts.find(row => row.customer_id === customerId) ?? null; },
  async getPrediction(predictionId, signal) { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return fixtureAccounts.find(row => row.prediction?.prediction_id === predictionId) ?? null; },
};

export class NotConnectedError extends Error {
  readonly code = 'NOT_CONNECTED';
  constructor(message: string) { super(message); this.name = 'NotConnectedError'; }
}

let backendAccountsPromise: Promise<AccountRecord[]> | null = null;

async function loadBackendAccounts(signal?: AbortSignal): Promise<AccountRecord[]> {
  if (!backendAccountsPromise) {
    backendAccountsPromise = getBackendDashboardAccounts(signal)
      .then(response => Promise.all(response.accounts.map(account => routeAccountThroughBackend(account, signal))))
      .catch(error => {
        backendAccountsPromise = null;
        throw error;
      });
  }
  const rows = await backendAccountsPromise;
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  return structuredClone(rows);
}

export const connectedDataSource: RetainIQDataSource = {
  listAccounts: loadBackendAccounts,
  async getAccount(customerId, signal) {
    return (await loadBackendAccounts(signal)).find(row => row.customer_id === customerId) ?? null;
  },
  async getPrediction(predictionId, signal) {
    return (await loadBackendAccounts(signal)).find(row => row.prediction?.prediction_id === predictionId) ?? null;
  },
};

export function accountDataSource(mode: DataMode): RetainIQDataSource {
  return mode === 'demo_fixture' ? fixtureDataSource : connectedDataSource;
}

// Kept as a compatibility alias for tests and fixture-only utilities. UI hooks must select a mode explicitly.
export const retainIQService: RetainIQDataSource = fixtureDataSource;
