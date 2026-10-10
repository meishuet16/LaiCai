import type { DataMode } from '../domain/customer.ts';
import type { IntegrationOverview } from '../domain/integration.ts';
import { NotConnectedError } from './retainIQService.ts';

const fixtureOverview: IntegrationOverview = {
  evidence_kind: 'demo_fixture',
  sources: [
    { category: 'usage', source: 'product_app', status: 'healthy', event_types: ['usage_aggregate_updated'], last_success_at: '2026-09-30T08:58:00Z', last_attempt_at: '2026-09-30T08:58:00Z', latest_occurred_at: '2026-09-30T08:54:00Z', latest_available_at: '2026-09-30T08:58:00Z', processed_count: 12840, rejected_count: 3, error_count: 0, freshness: 'fresh', mapping_version: 'map_v1', available_from: '2026-07-01', available_through: '2026-09-30' },
    { category: 'billing', source: 'billing', status: 'warning', event_types: ['payment_failed', 'payment_succeeded', 'invoice_payment_failed', 'invoice_paid'], last_success_at: '2026-09-29T02:00:00Z', last_attempt_at: '2026-09-30T08:30:00Z', latest_occurred_at: '2026-09-29T01:42:00Z', latest_available_at: '2026-09-29T02:00:00Z', processed_count: 4230, rejected_count: 0, error_count: 1, freshness: 'stale', mapping_version: 'map_v1', available_from: '2026-07-01', available_through: '2026-09-29' },
    { category: 'subscription', source: 'subscriptions', status: 'healthy', event_types: ['subscription_created', 'subscription_updated', 'cancellation_requested', 'subscription_cancelled_effective', 'subscription_non_renewed_effective', 'subscription_involuntary_terminated'], last_success_at: '2026-09-30T08:48:00Z', last_attempt_at: '2026-09-30T08:48:00Z', latest_occurred_at: '2026-09-30T08:46:00Z', latest_available_at: '2026-09-30T08:48:00Z', processed_count: 1940, rejected_count: 1, error_count: 0, freshness: 'fresh', mapping_version: 'map_v2', available_from: '2026-06-15', available_through: '2026-09-30' },
  ],
  coverage: { accounts_mapped: 1142, accounts_unmatched: 8, active_paying: 1098, missing_mrr: 14, incomplete_subscription_history: 26, usage_percent: 96, billing_percent: 91, subscription_percent: 99 },
  rejected_events: [
    { id: 'reject_01', at: '2026-09-30T08:40:00Z', source: 'product_app', source_event_id: 'evt_901', reason: 'Unknown account mapping', schema_version: '1.0', mapping_version: 'map_v1', redacted_metadata: 'event_type=usage_aggregate_updated; identifiers redacted' },
    { id: 'reject_02', at: '2026-09-30T08:32:00Z', source: 'subscriptions', source_event_id: 'evt_455', reason: 'Conflicting account identity', schema_version: '1.0', mapping_version: 'map_v2', redacted_metadata: 'event_type=subscription_created; identifiers redacted' },
  ],
  alerts: [
    { id: 'alert_billing', severity: 'warning', title: 'Billing source is delayed', detail: 'The sample fixture shows billing availability ending before the other sample sources.', source: 'billing' },
    { id: 'alert_identity', severity: 'warning', title: 'Identity conflicts need review', detail: 'Unmatched records remain quarantined; no account merge was inferred.', source: 'subscriptions' },
    { id: 'alert_outcome', severity: 'warning', title: 'Outcome coverage is incomplete', detail: 'Historical subscription gaps can leave forecast feedback pending or incomplete.', source: 'subscriptions' },
  ],
};

export interface IntegrationDataSource { getOverview(signal?: AbortSignal): Promise<IntegrationOverview> }
export const fixtureIntegrationService: IntegrationDataSource = {
  async getOverview(signal) { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return fixtureOverview; },
};
export const connectedIntegrationService: IntegrationDataSource = {
  async getOverview() { throw new NotConnectedError('Integration health requires an authenticated backend-for-frontend; no browser-safe health API is connected.'); },
};
export function integrationDataSource(mode: DataMode): IntegrationDataSource {
  return mode === 'demo_fixture' ? fixtureIntegrationService : connectedIntegrationService;
}
