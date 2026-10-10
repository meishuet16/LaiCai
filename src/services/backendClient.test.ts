import assert from 'node:assert/strict';
import test from 'node:test';
import type { AccountRecord } from '../domain/customer.ts';
import { routeAccountThroughBackend } from './backendClient.ts';

const account: AccountRecord = {
  tenant_id: 'tenant-01',
  customer_id: 'c02', name: 'Kopi Ventures', segment: 'SMB', plan: 'Starter',
  account_created_at: null, industry: null, region: null, acquisition_channel: null,
  onboarding_cohort: null, subscription_state: 'active', tenure_days: null,
  mrr: { amount_minor: 10000, currency: 'MYR' }, owner: null,
  case_id: 'demo_case_c02', case_status: 'Proposed', next_step: 'Review',
  route: 'OBSERVE', route_reason: 'fixture', exposure_proxy: null,
  evidence_kind: 'source_backed', data_origin: 'backend_dataset',
  prediction: {
    tenant_id: 'tenant-01', customer_id: 'c02', prediction_id: 'demo_pred_c02', prediction_run_id: 'demo_run',
    as_of: '2026-10-10T00:00:00Z', generated_at: '2026-10-10T00:00:10Z', status: 'scored',
    p_churn_7d: 0.3, p_churn_14d: 0.45, p_churn_30d: 0.7,
    feature_version: 'demo_features_v1', model_version: 'demo_model_v1', calibration_version: 'demo_calibration_v1', label_policy_version: 'demo_policy_v1',
    reliability: { status: 'sufficient_evidence', reasons: [] },
    data_freshness: { status: 'fresh', input_data_as_of: '2026-10-10T00:00:00Z', stale_sources: [] },
    uncertainty: { status: 'not_quantified', method: 'none', intervals: null }, explanations_by_horizon: {}, risk_bands_by_horizon: null,
  },
};

test('frontend account adapter uses the Python routing response', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (_input, init) => {
    const headers = new Headers(init?.headers);
    assert.equal(headers.get('X-Tenant-Id'), 'tenant-01');
    assert.equal((JSON.parse(String(init?.body)) as { customer_id: string }).customer_id, 'c02');
    return new Response(JSON.stringify({
      customer_id: 'c02', prediction_id: 'demo_pred_c02', route: 'PRIORITY_REVIEW',
      route_reason: 'eligible_sufficient_evidence_above_threshold', exposure_proxy_30d_minor: 7000, currency: 'MYR',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
  try {
    const routed = await routeAccountThroughBackend(account);
    assert.equal(routed.route, 'PRIORITY_REVIEW');
    assert.equal(routed.exposure_proxy?.amount_minor, 7000);
    assert.equal(routed.route_reason, 'eligible_sufficient_evidence_above_threshold');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
