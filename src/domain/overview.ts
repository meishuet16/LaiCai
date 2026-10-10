import type { AccountRecord, Currency, Freshness, Horizon, Money } from './customer';
import type { DecisionCase } from './decision';
import type { IntegrationOverview } from './integration';

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
  overdueCases: number;
  knownCancellations: number;
  abstained: number;
  insufficientEvidence: number;
  riskCounts: Record<'low' | 'medium' | 'high', number>;
  notForecasted: number;
  exposureByCurrency: Partial<Record<Currency, Money>>;
  exposureAccountCount: number;
  myrReportedMrr: Money | null;
  myrAccountCount: number;
  sgdAccountCount: number;
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

export function summarizeOverview(accounts: AccountRecord[], cases: DecisionCase[], integration: IntegrationOverview, asOf: string, horizon: Horizon): OverviewSummary {
  const riskCounts = { low: 0, medium: 0, high: 0 };
  let validPredictions = 0;
  for (const account of accounts) {
    const probability = probabilityFor(account, horizon);
    if (probability == null) continue;
    validPredictions += 1;
    if (probability < .3) riskCounts.low += 1;
    else if (probability < .6) riskCounts.medium += 1;
    else riskCounts.high += 1;
  }

  const exposureByCurrency: Partial<Record<Currency, Money>> = {};
  for (const account of accounts) {
    const exposure = account.exposure_proxy;
    if (!exposure) continue;
    const current = exposureByCurrency[exposure.currency];
    exposureByCurrency[exposure.currency] = { currency: exposure.currency, amount_minor: (current?.amount_minor ?? 0) + exposure.amount_minor };
  }

  const myrAccounts = accounts.filter(account => account.mrr?.currency === 'MYR');
  const myrReportedMrr = myrAccounts.length
    ? { currency: 'MYR' as const, amount_minor: myrAccounts.reduce((total, account) => total + (account.mrr?.amount_minor ?? 0), 0) }
    : null;
  const inputFreshness = Object.fromEntries((['fresh', 'partially_stale', 'stale', 'unknown'] as Freshness[]).map(status => [status, 0])) as Record<Freshness, number>;
  for (const account of accounts) inputFreshness[account.prediction?.data_freshness.status ?? 'unknown'] += 1;
  const sourceFreshness = Object.fromEntries((['fresh', 'stale', 'unknown'] as const).map(status => [status, 0])) as Record<'fresh' | 'stale' | 'unknown', number>;
  for (const source of integration.sources) sourceFreshness[source.freshness] += 1;

  const accountById = new Map(accounts.map(account => [account.customer_id, account]));
  const activities: OverviewActivity[] = [];
  const runs = new Map<string, { at: string; modelVersion: string; scored: number; abstained: number }>();
  for (const account of accounts) {
    const prediction = account.prediction;
    if (!prediction?.prediction_run_id) continue;
    const run = runs.get(prediction.prediction_run_id) ?? { at: prediction.generated_at, modelVersion: prediction.model_version, scored: 0, abstained: 0 };
    if (prediction.generated_at > run.at) run.at = prediction.generated_at;
    if (prediction.status === 'scored') run.scored += 1;
    if (prediction.status === 'abstained') run.abstained += 1;
    runs.set(prediction.prediction_run_id, run);
  }
  for (const [runId, run] of runs) {
    activities.push({
      id: `prediction:${runId}`,
      at: run.at,
      title: 'Prediction outputs available',
      detail: `${run.scored} scored · ${run.abstained} abstained · ${run.modelVersion}`,
      target: { type: 'prediction' },
    });
  }
  for (const item of cases) {
    const customer = accountById.get(item.customer_id);
    for (const entry of item.audit) activities.push({
      id: `case:${item.id}:${entry.id}`,
      at: entry.at,
      title: auditTitle(entry.type),
      detail: `${customer?.name ?? item.customer_id} · ${entry.actor}`,
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
    overdueCases: cases.filter(item => item.due_at != null && item.due_at < asOf && !terminalStatuses.includes(item.status)).length,
    knownCancellations: accounts.filter(account => account.route === 'KNOWN_CANCELLATION' || account.prediction?.status === 'known_cancellation').length,
    abstained: accounts.filter(account => account.prediction?.status === 'abstained').length,
    insufficientEvidence: accounts.filter(account => account.prediction?.reliability.status === 'insufficient_evidence').length,
    riskCounts,
    notForecasted: Math.max(0, accounts.length - validPredictions),
    exposureByCurrency,
    exposureAccountCount: accounts.filter(account => account.exposure_proxy != null).length,
    myrReportedMrr,
    myrAccountCount: myrAccounts.length,
    sgdAccountCount: accounts.filter(account => account.mrr?.currency === 'SGD').length,
    missingMrr: accounts.filter(account => account.mrr == null).length,
    sourceFreshness,
    inputFreshness,
    modelVersions: [...new Set(accounts.flatMap(account => account.prediction?.status === 'scored' ? [account.prediction.model_version] : []))].sort(),
    // The service's existing order is retained; this view does not calculate or imply a client-side rank.
    priorityCases: cases.filter(item => item.route === 'PRIORITY_REVIEW').slice(0, 5),
    recentActivity: activities.slice(0, 8),
  };
}
