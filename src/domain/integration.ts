export type SourceStatus = 'healthy' | 'warning' | 'failed' | 'unknown';
export const CANONICAL_EVENT_TYPES = [
  'session_started', 'feature_used', 'usage_aggregate_updated',
  'payment_failed', 'payment_succeeded', 'invoice_payment_failed', 'invoice_paid',
  'subscription_created', 'subscription_updated', 'cancellation_requested',
  'subscription_cancelled_effective', 'subscription_non_renewed_effective', 'subscription_involuntary_terminated',
] as const;
export type CanonicalEventType = typeof CANONICAL_EVENT_TYPES[number];
export type SourceHealth = {
  category: 'usage' | 'billing' | 'subscription'; source: string; status: SourceStatus; event_types: CanonicalEventType[];
  last_success_at: string | null; last_attempt_at: string | null;
  latest_occurred_at: string | null; latest_available_at: string | null;
  processed_count: number; rejected_count: number; error_count: number;
  freshness: 'fresh' | 'stale' | 'unknown'; mapping_version: string;
  available_from: string | null; available_through: string | null;
};
export type Coverage = {
  accounts_mapped: number; accounts_unmatched: number; active_paying: number;
  missing_mrr: number; incomplete_subscription_history: number;
  usage_percent: number | null; billing_percent: number | null; subscription_percent: number | null;
};
export type RejectedEvent = {
  id: string; at: string; source: string; source_event_id: string;
  reason: string; schema_version: string; mapping_version: string;
  redacted_metadata: string;
};
export type DataAlert = { id: string; severity: 'warning' | 'error'; title: string; detail: string; source: string | null };
export type IntegrationOverview = {
  sources: SourceHealth[]; coverage: Coverage; rejected_events: RejectedEvent[];
  alerts: DataAlert[]; evidence_kind: 'demo_fixture' | 'source_backed';
};
