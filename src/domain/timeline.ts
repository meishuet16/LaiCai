import type { AccountRecord, Horizon } from './customer';
import type { DecisionCase } from './decision';

export type TimelineCategory = 'source' | 'prediction' | 'decision' | 'action';
export type TimelineEvent = {
  id: string; category: TimelineCategory; title: string; summary: string;
  occurred_at: string; available_at: string; source: string;
  source_record_id: string | null; prediction_id: string | null; case_id: string | null;
  policy_version: string | null; fact_ids: string[]; details: string[];
  provenance: 'synthetic_source_fixture' | 'synthetic_prediction_fixture' | 'synthetic_case_audit' | 'synthetic_case_snapshot';
};
export type TimelineRecord = { account: AccountRecord; case: DecisionCase | null; events: TimelineEvent[]; evidence_kind: 'synthetic' };
// NOT_CONNECTED is a UI availability marker, not a canonical feedback label.
export type FeedbackState = 'PENDING' | 'NOT_CONNECTED' | 'INELIGIBLE';

export function visibleTimelineEvents(events: TimelineEvent[], cutoff: string | null): TimelineEvent[] {
  const bound = cutoff ? Date.parse(cutoff) : Date.now();
  if (Number.isNaN(bound)) return [];
  return events.filter(event => Date.parse(event.occurred_at) <= bound && Date.parse(event.available_at) <= bound)
    .sort((a, b) => Date.parse(a.occurred_at) - Date.parse(b.occurred_at) || a.id.localeCompare(b.id));
}

export function feedbackAt(account: AccountRecord, horizon: Horizon, cutoff: string | null): { state: FeedbackState; matures_at: string | null } | null {
  const prediction = account.prediction;
  if (!prediction) return null;
  if (cutoff && Date.parse(prediction.generated_at) > Date.parse(cutoff)) return null;
  if (prediction.status === 'known_cancellation' || prediction.status === 'not_eligible') return { state: 'INELIGIBLE', matures_at: null };
  const matures_at = new Date(Date.parse(prediction.as_of) + horizon * 86400000).toISOString();
  const viewTime = cutoff ? Date.parse(cutoff) : Date.now();
  return { state: viewTime < Date.parse(matures_at) ? 'PENDING' : 'NOT_CONNECTED', matures_at };
}
