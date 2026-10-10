import { useState } from 'react';
import { useApp } from '../app/AppContext';
import { casePath } from '../app/routes';
import { customerLabel, type Route } from '../domain/customer';
import type { DecisionCase } from '../domain/decision';
import { formatMoney, formatRisk } from '../domain/format';
import { useCustomers } from '../hooks/useCustomers';
import { useDecisionCases } from '../hooks/useDecisionCases';
import { EvidencePills } from '../components/StatusPills';
import { StrategyRoiSimulator } from './StrategyRoiSimulator';

const routes: Route[] = ['PRIORITY_REVIEW', 'HUMAN_REVIEW', 'OBSERVE', 'KNOWN_CANCELLATION', 'NOT_ELIGIBLE'];
const routeLabel = (value: string) => value.replaceAll('_', ' ').toLowerCase();
const routeTone = (route: Route) => route === 'HUMAN_REVIEW' ? 'red' : route === 'PRIORITY_REVIEW' ? 'amber' : 'neutral';
const routeDisplay = (route: Route) => route === 'HUMAN_REVIEW' ? 'HITL' : routeLabel(route);
const statusTones: Record<DecisionCase['status'], string> = {
  PROPOSED: 'amber', HUMAN_REVIEWED: 'amber', ASSIGNED: 'good', EXECUTED: 'good',
  FOLLOW_UP_DUE: 'amber', FOLLOW_UP_COMPLETE: 'good', DEFERRED: 'neutral', REJECTED: 'red',
  CLOSED_NO_ACTION: 'neutral', CANCELLED: 'neutral', FAILED: 'red', OBSERVE: 'neutral',
  KNOWN_CANCELLATION: 'neutral', NOT_ELIGIBLE: 'neutral',
};
const statusLabels: Partial<Record<DecisionCase['status'], string>> = {
  HUMAN_REVIEWED: 'reviewed', FOLLOW_UP_DUE: 'follow-up', FOLLOW_UP_COMPLETE: 'complete',
  CLOSED_NO_ACTION: 'closed', KNOWN_CANCELLATION: 'cancelled', NOT_ELIGIBLE: 'ineligible',
};
type MainTab = 'queue' | 'strategy';
type RouteFilter = Route | 'ALL';

export function DecisionCasesPage() {
  const { navigate, query, setQuery, currency } = useApp();
  const { cases, capacity, status, error } = useDecisionCases();
  const accounts = useCustomers();
  const [mainTab, setMainTab] = useState<MainTab>('queue');
  const [route, setRoute] = useState<RouteFilter>('PRIORITY_REVIEW');

  if (status === 'loading' || accounts.status === 'loading') return <p role="status">Loading retention work…</p>;
  if (status === 'unavailable' || accounts.status === 'unavailable') return <section className="card unavailable-state"><h2>Retention Actions is not connected</h2><p>{error ?? accounts.error}</p><p>The active backend has no decision-case, budget, capacity, or approval APIs. Connected mode does not simulate prioritization or approvals.</p></section>;
  if (status === 'error' || accounts.status === 'error' || !capacity) return <div className="notice ambernote" role="alert">{error ?? accounts.error ?? 'Retention work is unavailable.'}</div>;
  const byId = new Map(accounts.rows.map(row => [row.customer_id, row]));
  const visible = cases.filter(item => (route === 'ALL' || item.route === route) && byId.has(item.customer_id) && (currency === 'All' || byId.get(item.customer_id)?.mrr?.currency === currency || byId.get(item.customer_id)?.mrr == null) && `${item.id} ${item.customer_id}`.toLowerCase().includes(query.toLowerCase()));
  const ranked = [...visible].sort((a, b) => {
    const left = byId.get(a.customer_id)?.exposure_proxy;
    const right = byId.get(b.customer_id)?.exposure_proxy;
    if (!left && !right) return a.created_at.localeCompare(b.created_at);
    if (!left) return 1;
    if (!right) return -1;
    if (left.currency !== right.currency) return left.currency.localeCompare(right.currency);
    return right.amount_minor - left.amount_minor;
  });
  const queuedForReview = cases.filter(item => ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)).length;
  const clearFilterQuery = () => setRoute('PRIORITY_REVIEW');

  return <>
    <div className="notice bluenote">Human-governed workflow. Decisions, capacity checks and audit entries are persisted; approval records a task but never sends customer communication automatically.</div>
    <div className="page-tabs" role="tablist" aria-label="Retention Actions views"><button role="tab" aria-selected={mainTab === 'queue'} onClick={() => setMainTab('queue')}>Work Queue <span>{queuedForReview} awaiting review</span></button><button role="tab" aria-selected={mainTab === 'strategy'} onClick={() => setMainTab('strategy')}>Strategy &amp; ROI Simulator <span>Scenario only</span></button></div>

    {mainTab === 'queue' ? <>
      <section className="metrics capacity-metrics" aria-label="Review capacity and workload">
        <article className="quick"><small>Review capacity</small><strong>{capacity.review_slots - capacity.used_review_slots} / {capacity.review_slots}</strong><span>Available slots / total</span></article>
        <article className="quick"><small>Awaiting review</small><strong>{capacity.pending}</strong><span>Includes {capacity.investigation_queue} human investigations</span></article>
        <article className="quick alert"><small>Overdue cases</small><strong>{capacity.overdue ?? 'N/A'}</strong><span>{capacity.overdue == null ? 'No authorized as-of cutoff' : 'At the current review cutoff'}</span></article>
        <article className="quick"><small>Staff minutes remaining</small><strong>{Math.max(0, capacity.staff_minutes_total - capacity.staff_minutes_used)}</strong><span>Of {capacity.staff_minutes_total} available minutes</span></article>
      </section>
      <section className="card"><div className="section-head"><div><h2>Budget by currency</h2><p className="muted">Reserved action budget is checked independently for each currency.</p></div></div><div className="budget-grid">{capacity.budgets.map(limit => { const used = capacity.budget_used.find(value => value.currency === limit.currency)?.amount_minor ?? 0; return <div key={limit.currency}><small>{limit.currency} · allocation</small><b>{formatMoney({ amount_minor: Math.max(0, limit.amount_minor - used), currency: limit.currency })} remaining</b><span>{formatMoney({ amount_minor: used, currency: limit.currency })} allocated / {formatMoney(limit)} total</span></div>; })}</div></section>
      <section className="card stage-section"><div className="section-head"><div><h2>Prioritized work queue</h2><p className="muted">Route tabs group cases. Within each route, currency comes first, then exposure.</p></div><span className="pill neutral">{ranked.length} cases</span></div>
        <div className="case-tabs route-tabs" role="tablist" aria-label="Decision routes"><button type="button" role="tab" aria-selected={route === 'ALL'} onClick={() => setRoute('ALL')}>All cases <b>{cases.length}</b><small>{queuedForReview} pending</small></button>{routes.map(value => { const routeCases = cases.filter(item => item.route === value); const awaiting = routeCases.filter(item => ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)).length; return <button key={value} type="button" role="tab" aria-selected={route === value} onClick={() => setRoute(value)}>{routeLabel(value)} <b>{routeCases.length}</b><small>{awaiting} pending</small></button>; })}</div>
        <div className="filters"><input aria-label="Search retention cases" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search customer or case ID"/><button className="btn outline" onClick={() => { setQuery(''); clearFilterQuery(); }}>Clear</button></div>
        {ranked.length ? <div className="tablewrap"><table className="work-queue-table"><thead><tr><th>Customer</th><th>Risk · 7d / 30d</th><th>Evidence</th><th>MRR / at risk</th><th>Facts</th><th>Route / next step</th><th>Status</th><th>Open</th></tr></thead><tbody>{ranked.map((item, index) => { const account = byId.get(item.customer_id)!; const recommendation = item.proposed_action ? routeLabel(item.proposed_action) : 'No next step'; return <tr key={item.id}><td><b>#{index + 1} · {customerLabel(account)}</b><small>{account.customer_id} · {account.segment ?? 'Segment unavailable'}</small></td><td>{formatRisk(account.prediction, 7)} / {formatRisk(account.prediction, 30)}</td><td><EvidencePills reliability={account.prediction?.reliability.status} freshness={account.prediction?.data_freshness.status} compact/></td><td>{formatMoney(account.mrr)}<small>At risk: {formatMoney(account.exposure_proxy)}</small></td><td>{item.fact_ids.length} {item.fact_ids.length === 1 ? 'fact' : 'facts'}<small>{item.warnings.length ? `${item.warnings.length} ${item.warnings.length === 1 ? 'warning' : 'warnings'}` : 'No warnings'}</small></td><td><div className="queue-route"><span className={`pill ${routeTone(item.route)}`} title={routeLabel(item.route)} aria-label={item.route === 'HUMAN_REVIEW' ? 'Human in the loop' : routeLabel(item.route)}>{routeDisplay(item.route)}</span><small>{recommendation}</small></div></td><td><span className={`pill ${statusTones[item.status]}`} title={routeLabel(item.status)}>{statusLabels[item.status] ?? routeLabel(item.status)}</span></td><td><button className="btn outline table-action" onClick={() => navigate(casePath(item.id))}>Open case</button></td></tr>; })}</tbody></table></div> : <p className="empty-trend">No cases match the filters.</p>}
        <p className="caption">At-risk proxy = p30 × MRR, not saved revenue. Missing values remain unknown.</p></section>
    </> : <StrategyRoiSimulator accounts={accounts.rows} cases={cases} capacity={capacity} />}
  </>;
}
