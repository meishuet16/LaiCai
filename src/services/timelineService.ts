import type { CanonicalEventType } from '../domain/integration.ts';
import type { TimelineEvent, TimelineRecord } from '../domain/timeline.ts';
import type { DataMode } from '../domain/customer.ts';
import { decisionService } from './decisionService.ts';
import { fixtureDataSource, NotConnectedError } from './retainIQService.ts';

type SourceFixture = { customer_id: string; id: string; source: string; title: string; summary: string; occurred_at: string; available_at: string; fact_ids: string[] };
// Redacted examples only. Occurrence and source availability are independent timestamps.
const sourceFixtures: SourceFixture[] = [
  { customer_id: 'c01', id: 'demo_src_c01_payment_1', source: 'billing', title: 'Payment failure received', summary: 'Redacted payment-failure metadata; no credential or payment instrument.', occurred_at: '2026-10-07T08:00:00Z', available_at: '2026-10-07T08:04:00Z', fact_ids: ['billing_evt_101'] },
  { customer_id: 'c01', id: 'demo_src_c01_payment_2', source: 'billing', title: 'Second payment failure received', summary: 'Second redacted billing event in the synthetic 30-day window.', occurred_at: '2026-10-08T07:00:00Z', available_at: '2026-10-08T07:05:00Z', fact_ids: ['billing_evt_102'] },
  { customer_id: 'c02', id: 'demo_src_c02_usage', source: 'product_app', title: 'Usage summary available', summary: 'Synthetic activity summary was below the account baseline.', occurred_at: '2026-10-08T09:00:00Z', available_at: '2026-10-08T09:03:00Z', fact_ids: ['usage_fact_201'] },
  { customer_id: 'c02', id: 'demo_src_c02_late', source: 'product_app', title: 'Late-arriving usage event', summary: 'Occurred before prediction cutoff but became available afterward; not eligible as an earlier feature.', occurred_at: '2026-10-09T23:00:00Z', available_at: '2026-10-10T01:00:00Z', fact_ids: [] },
  { customer_id: 'c03', id: 'demo_src_c03_session', source: 'product_app', title: 'Last observed session', summary: 'Synthetic last session before the inactivity period.', occurred_at: '2026-09-29T10:00:00Z', available_at: '2026-09-29T10:02:00Z', fact_ids: ['usage_fact_301'] },
  { customer_id: 'c04', id: 'demo_src_c04_quality', source: 'billing', title: 'Billing coverage warning', summary: 'Synthetic billing history is stale and account history is short.', occurred_at: '2026-10-08T07:00:00Z', available_at: '2026-10-08T07:15:00Z', fact_ids: ['quality_fact_401'] },
  { customer_id: 'c05', id: 'demo_src_c05_usage', source: 'product_app', title: 'Usage summary available', summary: 'Synthetic activity remains near the account baseline.', occurred_at: '2026-10-08T11:00:00Z', available_at: '2026-10-08T11:05:00Z', fact_ids: ['usage_fact_501'] },
  { customer_id: 'c06', id: 'demo_src_c06_cancel', source: 'subscriptions', title: 'Cancellation request known', summary: 'Synthetic request was available before the prediction cutoff; this account is not prospectively scored.', occurred_at: '2026-10-09T06:00:00Z', available_at: '2026-10-09T06:05:00Z', fact_ids: ['subscription_evt_601'] },
  { customer_id: 'c07', id: 'demo_src_c07_identity', source: 'subscriptions', title: 'Identity conflict quarantined', summary: 'Synthetic conflicting mapping; restricted identifiers are omitted.', occurred_at: '2026-10-09T07:00:00Z', available_at: '2026-10-09T07:15:00Z', fact_ids: ['quality_fact_701'] },
  { customer_id: 'c08', id: 'demo_src_c08_usage', source: 'product_app', title: 'Usage summary available', summary: 'Synthetic activity is below the account baseline.', occurred_at: '2026-10-08T06:00:00Z', available_at: '2026-10-08T06:05:00Z', fact_ids: ['usage_fact_801'] },
  { customer_id: 'c09', id: 'demo_src_c09_trial', source: 'subscriptions', title: 'Trial state available', summary: 'Synthetic account has no active paid subscription.', occurred_at: '2026-10-08T06:00:00Z', available_at: '2026-10-08T06:05:00Z', fact_ids: ['subscription_fact_901'] },
];

function sourceEvents(customerId: string): TimelineEvent[] {
  const eventTypes: Record<string, CanonicalEventType | null> = {
    demo_src_c01_payment_1: 'payment_failed', demo_src_c01_payment_2: 'payment_failed',
    demo_src_c02_usage: 'usage_aggregate_updated', demo_src_c02_late: 'usage_aggregate_updated',
    demo_src_c03_session: 'usage_aggregate_updated', demo_src_c04_quality: null,
    demo_src_c05_usage: 'usage_aggregate_updated', demo_src_c06_cancel: 'cancellation_requested',
    demo_src_c07_identity: null, demo_src_c08_usage: 'usage_aggregate_updated', demo_src_c09_trial: null,
  };
  return sourceFixtures.filter(item => item.customer_id === customerId).map(item => ({ id: item.id, category: 'source', title: item.title, canonical_event_type: eventTypes[item.id] ?? null, summary: item.summary, occurred_at: item.occurred_at, available_at: item.available_at, source: item.source, source_record_id: item.id, prediction_id: null, case_id: null, policy_version: null, fact_ids: item.fact_ids, details: [item.summary, 'Raw source record and restricted fields are not connected.'], provenance: 'synthetic_source_fixture' }));
}

export interface TimelineDataSource { getTimeline(customerId: string, signal?: AbortSignal): Promise<TimelineRecord | null> }
export const fixtureTimelineService: TimelineDataSource = {
  async getTimeline(customerId: string, signal?: AbortSignal): Promise<TimelineRecord | null> {
    const [account, item] = await Promise.all([fixtureDataSource.getAccount(customerId, signal), decisionService.getCase(`demo_case_${customerId}`, signal)]);
    if (!account) return null;
    const events = sourceEvents(customerId);
    const prediction = account.prediction;
    if (prediction?.generated_at) events.push({ id: prediction.prediction_id, category: 'prediction', title: prediction.status === 'scored' ? 'Sample prediction snapshot' : 'Sample prediction route status', canonical_event_type: null, summary: prediction.status === 'scored' ? 'Untrained demo fixture probabilities; not a model output.' : `Demo fixture ${prediction.status.replaceAll('_', ' ')} state; probabilities are unavailable.`, occurred_at: prediction.generated_at, available_at: prediction.generated_at, source: 'demo_fixture', source_record_id: null, prediction_id: prediction.prediction_id, case_id: null, policy_version: prediction.label_policy_version, fact_ids: [], details: [`As-of cutoff: ${prediction.as_of ?? 'not source-backed'}`, `Model: ${prediction.model_version ?? 'not connected'}; features: ${prediction.feature_version ?? 'not connected'}; calibration: ${prediction.calibration_version ?? 'not connected'}`, `Reliability: ${prediction.reliability.status}; freshness: ${prediction.data_freshness.status}`], provenance: 'synthetic_prediction_fixture' });
    if (item) {
      for (const entry of item.audit) events.push({ id: entry.id, category: ['EXECUTED', 'CANCELLED', 'FAILED', 'FOLLOW_UP_COMPLETE'].includes(entry.type) ? 'action' : 'decision', title: entry.type.replaceAll('_', ' '), canonical_event_type: null, summary: entry.detail, occurred_at: entry.at, available_at: entry.at, source: 'case_audit_fixture', source_record_id: null, prediction_id: null, case_id: item.id, policy_version: 'demo_policy_v1', fact_ids: item.fact_ids, details: [`Actor: ${entry.actor}`, `Recorded decision/audit type: ${entry.type}`, 'This case event is not linked to the displayed prediction ID; prior workflow history is incomplete.'], provenance: 'synthetic_case_audit' });
      if (item.completed_at && item.selected_action) events.push({ id: `demo_action_${item.customer_id}_${item.completed_at}`, category: 'action', title: `${item.selected_action.replaceAll('_', ' ')} ${item.status === 'FAILED' ? 'failed' : item.status === 'CANCELLED' ? 'cancelled' : 'recorded'}`, canonical_event_type: null, summary: 'Synthetic execution snapshot; no external outreach or payment action was performed by this frontend.', occurred_at: item.completed_at, available_at: item.completed_at, source: 'case_snapshot_fixture', source_record_id: null, prediction_id: null, case_id: item.id, policy_version: 'demo_policy_v1', fact_ids: item.fact_ids, details: [`Actual cost: ${item.actual_cost ? `${item.actual_cost.amount_minor} minor units ${item.actual_cost.currency}` : 'N/A'}`, `Actual effort: ${item.actual_minutes ?? 'N/A'} minutes`, `Follow-up anchor/due: ${item.follow_up_at ?? 'N/A'}`, 'Authoritative immutable execution event ID is not connected.'], provenance: 'synthetic_case_snapshot' });
    }
    return { account, case: item, events, evidence_kind: 'demo_fixture' };
  },
};

export const connectedTimelineService: TimelineDataSource = {
  async getTimeline() { throw new NotConnectedError('Customer timeline and point-in-time event APIs are not connected in this frontend.'); },
};

export function timelineDataSource(mode: DataMode): TimelineDataSource {
  return mode === 'demo_fixture' ? fixtureTimelineService : connectedTimelineService;
}
