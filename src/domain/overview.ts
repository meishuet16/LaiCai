import type { AccountRecord, Currency, Freshness, Horizon, Money } from './customer.ts';
import type { DecisionCase } from './decision.ts';
import type { IntegrationOverview } from './integration.ts';

export type OverviewActivityTarget =
  | { type: 'prediction' }
  | { type: 'case'; caseId: string; customerId: string }
  | { type: 'integration' };

export type OverviewActivity = {
  id: string;
  at: string;
  title: string;
  detail: string;
  target: OverviewActivityTarget;
};

export type OverviewSummary = {
  eligibleAccounts: number;
  validPredictions: number;
  openCases: number;
  pendingCases: number;
  overdueCases: number | null;
  knownCancellations: number;
  abstained: number;
  insufficientEvidence: number;
  predictionStatuses: Record<'scored' | 'abstained' | 'known_cancellation' | 'not_eligible', number>;
  notForecasted: number;
  exposureByCurrency: Partial<Record<Currency, Money>>;
  exposureAccountCount: number;
  mrrByCurrency: Partial<Record<Currency, Money>>;
  mrrAccountCounts: Partial<Record<Currency, number>>;
  missingMrr: number;
  sourceFreshness: Record<'fresh' | 'stale' | 'unknown', number>;
  inputFreshness: Record<Freshness, number>;
  modelVersions: string[];
  priorityCases: DecisionCase[];
  recentActivity: OverviewActivity[];
};

const terminalStatuses = ['REJECTED', 'CLOSED_NO_ACTION', 'CANCELLED', 'FAILED', 'FOLLOW_UP_COMPLETE', 'OBSERVE', 'KNOWN_CANCELLATION', 'NOT_ELIGIBLE'];
const pendingStatuses = ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'];
const excludedRoutes = ['OBSERVE', 'KNOWN_CANCELLATION', 'NOT_ELIGIBLE'];

function probabilityFor(account: AccountRecord, horizon: Horizon): number | null {
  const prediction = account.prediction;
  if (prediction?.status !== 'scored') return null;
  return horizon === 7 ? prediction.p_churn_7d : horizon === 14 ? prediction.p_churn_14d : prediction.p_churn_30d;
}

function auditTitle(type: string): string {
  const titles: Record<string, string> = {
    ROUTED: 'Decision route recorded',
    APPROVE: 'Human decision · approved',
    MODIFY: 'Human decision · modified',
    REJECT: 'Human decision · rejected',
    NO_INTERVENTION: 'Human decision · no intervention',
    DEFER: 'Case deferred',
    EXECUTED: 'Action execution recorded',
    CANCELLED: 'Action cancelled',
    FAILED: 'Action failed',
    FOLLOW_UP_COMPLETE: 'Follow-up completed',
  };
  return titles[type] ?? `Case activity · ${type.toLowerCase().replaceAll('_', ' ')}`;
}

export function summarizeOverview(accounts: AccountRecord[], cases: DecisionCase[], integration: IntegrationOverview, asOf: string | null, horizon: Horizon): OverviewSummary {
  const predictionStatuses = { scored: 0, abstained: 0, known_cancellation: 0, not_eligible: 0 };
  let validPredictions = 0;
  for (const account of accounts) {
    const status = account.prediction?.status;
    if (status && status in predictionStatuses) predictionStatuses[status as keyof typeof predictionStatuses] += 1;
    const probability = probabilityFor(account, horizon);
    if (probability == null) continue;
    validPredictions += 1;
  }

  const exposureByCurrency: Partial<Record<Currency, Money>> = {};
  for (const account of accounts) {
    const exposure = account.exposure_proxy;
    if (!exposure) continue;
    const current = exposureByCurrency[exposure.currency];
    exposureByCurrency[exposure.currency] = { currency: exposure.currency, amount_minor: (current?.amount_minor ?? 0) + exposure.amount_minor };
  }

  const mrrByCurrency: Partial<Record<Currency, Money>> = {};
  const mrrAccountCounts: Partial<Record<Currency, number>> = {};
  for (const account of accounts) {
    if (!account.mrr || !Number.isSafeInteger(account.mrr.amount_minor) || account.mrr.amount_minor < 0) continue;
    const currency = account.mrr.currency;
    const current = mrrByCurrency[currency];
    mrrByCurrency[currency] = { currency, amount_minor: (current?.amount_minor ?? 0) + account.mrr.amount_minor };
    mrrAccountCounts[currency] = (mrrAccountCounts[currency] ?? 0) + 1;
  }
  const inputFreshness = Object.fromEntries((['fresh', 'partially_stale', 'stale', 'unknown'] as Freshness[]).map(status => [status, 0])) as Record<Freshness, number>;
  for (const account of accounts) inputFreshness[account.prediction?.data_freshness.status ?? 'unknown'] += 1;
  const sourceFreshness = Object.fromEntries((['fresh', 'stale', 'unknown'] as const).map(status => [status, 0])) as Record<'fresh' | 'stale' | 'unknown', number>;
  for (const source of integration.sources) sourceFreshness[source.freshness] += 1;

  const accountById = new Map(accounts.map(account => [account.customer_id, account]));
  const activities: OverviewActivity[] = [];
  const runs = new Map<string, { at: string; modelVersion: string | null; scored: number; abstained: number }>();
  for (const account of accounts) {
    const prediction = account.prediction;
    if (!prediction?.prediction_run_id || !prediction.generated_at) continue;
    const run = runs.get(prediction.prediction_run_id) ?? { at: prediction.generated_at, modelVersion: prediction.model_version, scored: 0, abstained: 0 };
    if (run.at && prediction.generated_at > run.at) run.at = prediction.generated_at;
    if (prediction.status === 'scored') run.scored += 1;
    if (prediction.status === 'abstained') run.abstained += 1;
    runs.set(prediction.prediction_run_id, run);
  }
  for (const [runId, run] of runs) {
    activities.push({
      id: `prediction:${runId}`,
      at: run.at,
      title: 'Prediction outputs available',
      detail: `${run.scored} scored · ${run.abstained} abstained · ${run.modelVersion ?? 'model version unavailable'}`,
      target: { type: 'prediction' },
    });
  }
  for (const item of cases) {
    const customer = accountById.get(item.customer_id);
    for (const entry of item.audit) activities.push({
      id: `case:${item.id}:${entry.id}`,
      at: entry.at,
      title: auditTitle(entry.type),
      detail: `${customer?.customer_id ?? item.customer_id} · ${entry.actor}`,
      target: { type: 'case', caseId: item.id, customerId: item.customer_id },
    });
  }
  for (const event of integration.rejected_events) activities.push({
    id: `rejected:${event.id}`,
    at: event.at,
    title: 'Rejected source record',
    detail: `${event.source.replaceAll('_', ' ')} · ${event.reason}`,
    target: { type: 'integration' },
  });
  activities.sort((left, right) => Date.parse(right.at) - Date.parse(left.at) || left.id.localeCompare(right.id));

  return {
    eligibleAccounts: accounts.filter(account => !['KNOWN_CANCELLATION', 'NOT_ELIGIBLE'].includes(account.route)).length,
    validPredictions,
    openCases: cases.filter(item => !terminalStatuses.includes(item.status) && !excludedRoutes.includes(item.route)).length,
    pendingCases: cases.filter(item => pendingStatuses.includes(item.status)).length,
    overdueCases: asOf ? cases.filter(item => item.due_at != null && item.due_at < asOf && !terminalStatuses.includes(item.status)).length : null,
    knownCancellations: accounts.filter(account => account.route === 'KNOWN_CANCELLATION' || account.prediction?.status === 'known_cancellation').length,
    abstained: accounts.filter(account => account.prediction?.status === 'abstained').length,
    insufficientEvidence: accounts.filter(account => account.prediction?.reliability.status === 'insufficient_evidence').length,
    predictionStatuses,
    notForecasted: Math.max(0, accounts.length - validPredictions),
    exposureByCurrency,
    exposureAccountCount: accounts.filter(account => account.exposure_proxy != null).length,
    mrrByCurrency,
    mrrAccountCounts,
    missingMrr: accounts.filter(account => account.mrr == null).length,
    sourceFreshness,
    inputFreshness,
    modelVersions: [...new Set(accounts.flatMap(account => account.prediction?.status === 'scored' && account.prediction.model_version ? [account.prediction.model_version] : []))].sort(),
    // The service's existing order is retained; this view does not calculate or imply a client-side rank.
    priorityCases: cases.filter(item => item.route === 'PRIORITY_REVIEW').slice(0, 5),
    recentActivity: activities.slice(0, 8),
  };
}
