import type { AccountRecord, Currency, Horizon, Money, Route } from './customer.ts';
import type { ActionId, CaseStatus, DecisionCase } from './decision.ts';

export type DashboardRow = { account: AccountRecord; case: DecisionCase };
export type DashboardFilters = { horizon: Horizon; route: Route | 'all'; actionStatus: CaseStatus | 'all'; actionType: ActionId | 'all'; owner: string; segment: string; currency: Currency | 'All'; query: string };
export type DashboardSummary = {
  rows: DashboardRow[];
  eligible: number; scored: number; abstained: number; ineligible: number;
  routeCounts: Record<Route, number>;
  pending: number; overdue: number | null; openActions: number; followUpsDue: number | null;
  missingMrr: number; missingExposure: number;
  policyBands: { band: 'low' | 'medium' | 'high' | 'no_score' | 'unavailable'; count: number }[];
  exposureByCurrency: Money[];
  estimatedCostByCurrency: Money[]; actualCostByCurrency: Money[];
  missingActualCost: number; estimatedMinutes: number; actualMinutes: number; missingActualMinutes: number;
  actionCounts: { action: ActionId; count: number }[];
  ownerCounts: { owner: string; count: number }[];
  decisionCounts: { decision: string; count: number }[];
  firstResponseHours: number[];
};

const routes: Route[] = ['PRIORITY_REVIEW', 'HUMAN_REVIEW', 'OBSERVE', 'KNOWN_CANCELLATION', 'NOT_ELIGIBLE'];
const openStatuses: CaseStatus[] = ['ASSIGNED', 'EXECUTED', 'FOLLOW_UP_DUE'];
const costStatuses: CaseStatus[] = ['ASSIGNED', 'EXECUTED', 'FOLLOW_UP_DUE', 'FOLLOW_UP_COMPLETE', 'FAILED', 'CANCELLED'];
const decisionTypes = ['APPROVE', 'MODIFY', 'REJECT', 'NO_INTERVENTION', 'DEFER'];

export function selectDashboardRows(accounts: AccountRecord[], cases: DecisionCase[], filters: DashboardFilters): DashboardRow[] {
  const byCustomer = new Map(cases.map(item => [item.customer_id, item]));
  return accounts.flatMap(account => {
    const item = byCustomer.get(account.customer_id);
    if (!item) return [];
    if (filters.route !== 'all' && item.route !== filters.route) return [];
    if (filters.actionStatus !== 'all' && item.status !== filters.actionStatus) return [];
    if (filters.actionType !== 'all' && item.selected_action !== filters.actionType && item.proposed_action !== filters.actionType) return [];
    if (filters.owner !== 'all' && (filters.owner === 'unassigned' ? item.owner != null : item.owner !== filters.owner)) return [];
    if (filters.segment !== 'all' && account.segment !== filters.segment) return [];
    if (filters.currency !== 'All' && account.mrr?.currency !== filters.currency) return [];
    if (!account.customer_id.toLowerCase().includes(filters.query.toLowerCase())) return [];
    return [{ account, case: item }];
  });
}

export function summarizeDashboard(rows: DashboardRow[], horizon: Horizon, asOf: string | null): DashboardSummary {
  const routeCounts = Object.fromEntries(routes.map(route => [route, rows.filter(row => row.case.route === route).length])) as Record<Route, number>;
  const bands = ['low', 'medium', 'high', 'no_score', 'unavailable'] as const;
  const policyBands: DashboardSummary['policyBands'] = bands.map(band => ({ band, count: rows.filter(({ account }) => {
    if (band === 'no_score') return account.prediction?.status !== 'scored';
    if (band === 'unavailable') return account.prediction?.status === 'scored' && account.prediction.risk_bands_by_horizon?.[horizon] == null;
    return account.prediction?.status === 'scored' && account.prediction.risk_bands_by_horizon?.[horizon] === band;
  }).length }));
  const sumMoney = (pick: (row: DashboardRow) => Money | null): Money[] => [...new Set(rows.flatMap(row => { const value = pick(row); return value ? [value.currency] : []; }))].sort().map(currency => ({ currency, amount_minor: rows.reduce((sum, row) => { const value = pick(row); return sum + (value?.currency === currency ? value.amount_minor : 0); }, 0) }));
  const costly = rows.filter(row => costStatuses.includes(row.case.status) && row.case.selected_action);
  const decisionCounts = decisionTypes.map(decision => ({ decision, count: rows.reduce((sum, row) => sum + row.case.audit.filter(entry => entry.type === decision).length, 0) }));
  const actionTypes = [...new Set(rows.map(row => row.case.selected_action).filter((value): value is ActionId => value != null))];
  const owners = [...new Set(rows.map(row => row.case.owner ?? 'Unassigned'))];
  return {
    rows,
    eligible: rows.filter(row => !['KNOWN_CANCELLATION', 'NOT_ELIGIBLE'].includes(row.case.route)).length,
    scored: rows.filter(row => row.account.prediction?.status === 'scored').length,
    abstained: rows.filter(row => row.account.prediction?.status === 'abstained').length,
    ineligible: rows.filter(row => row.case.route === 'NOT_ELIGIBLE').length,
    routeCounts,
    pending: rows.filter(row => ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(row.case.status)).length,
    overdue: asOf ? rows.filter(row => row.case.due_at && row.case.due_at < asOf && !['REJECTED', 'CLOSED_NO_ACTION', 'CANCELLED', 'FOLLOW_UP_COMPLETE'].includes(row.case.status)).length : null,
    openActions: rows.filter(row => openStatuses.includes(row.case.status)).length,
    followUpsDue: asOf ? rows.filter(row => row.case.follow_up_at && row.case.follow_up_at < asOf && row.case.status !== 'FOLLOW_UP_COMPLETE').length : null,
    missingMrr: rows.filter(row => row.account.mrr == null && row.case.route !== 'NOT_ELIGIBLE').length,
    missingExposure: rows.filter(row => row.case.route === 'PRIORITY_REVIEW' && row.account.exposure_proxy == null).length,
    policyBands,
    exposureByCurrency: sumMoney(row => row.account.exposure_proxy),
    estimatedCostByCurrency: sumMoney(row => row.case.estimated_cost),
    actualCostByCurrency: sumMoney(row => row.case.actual_cost),
    missingActualCost: costly.filter(row => row.case.actual_cost == null).length,
    estimatedMinutes: costly.reduce((sum, row) => sum + row.case.estimated_minutes, 0),
    actualMinutes: costly.reduce((sum, row) => sum + (row.case.actual_minutes ?? 0), 0),
    missingActualMinutes: costly.filter(row => row.case.actual_minutes == null).length,
    actionCounts: actionTypes.map(action => ({ action, count: rows.filter(row => row.case.selected_action === action).length })),
    ownerCounts: owners.map(owner => ({ owner, count: rows.filter(row => (row.case.owner ?? 'Unassigned') === owner && ['PROPOSED', 'HUMAN_REVIEWED', 'ASSIGNED', 'DEFERRED', 'FOLLOW_UP_DUE'].includes(row.case.status)).length })),
    decisionCounts,
    firstResponseHours: rows.flatMap(row => row.case.response_at ? [(Date.parse(row.case.response_at) - Date.parse(row.case.created_at)) / 3600000] : []),
  };
}
