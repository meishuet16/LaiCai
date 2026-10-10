import { useState } from 'react';
import { useApp } from '../app/AppContext';
import { casePath } from '../app/routes';
import type { Route } from '../domain/customer';
import type { DecisionCase } from '../domain/decision';
import { formatDateTime, formatMoney, formatRisk } from '../domain/format';
import { useCustomers } from '../hooks/useCustomers';
import { useDecisionCases } from '../hooks/useDecisionCases';
import { EvidencePills } from '../components/StatusPills';
import { StrategyRoiSimulator } from './StrategyRoiSimulator';

const routes: Route[] = ['PRIORITY_REVIEW', 'HUMAN_REVIEW', 'OBSERVE', 'KNOWN_CANCELLATION', 'NOT_ELIGIBLE'];
const routeLabel = (value: string) => value.replaceAll('_', ' ').toLowerCase();
type MainTab = 'queue' | 'strategy';

export function DecisionCasesPage() {
  const { navigate, query, setQuery, currency } = useApp();
  const { cases, capacity, status, error } = useDecisionCases();
  const accounts = useCustomers();
  const [mainTab, setMainTab] = useState<MainTab>('queue');
  const [route, setRoute] = useState<Route>('PRIORITY_REVIEW');

  if (status === 'loading' || accounts.status === 'loading') return <p role="status">Loading retention work…</p>;
  if (status === 'unavailable' || accounts.status === 'unavailable') return <section className="card unavailable-state"><h2>Retention Actions is not connected</h2><p>{error ?? accounts.error}</p><p>The active backend has no decision-case, budget, capacity, or approval APIs. Connected mode does not simulate prioritization or approvals.</p></section>;
  if (status === 'error' || accounts.status === 'error' || !capacity) return <div className="notice ambernote" role="alert">{error ?? accounts.error ?? 'Retention work is unavailable.'}</div>;
  const byId = new Map(accounts.rows.map(row => [row.customer_id, row]));
  const visible = cases.filter(item => item.route === route && byId.has(item.customer_id) && (currency === 'All' || byId.get(item.customer_id)?.mrr?.currency === currency || byId.get(item.customer_id)?.mrr == null) && `${item.id} ${item.customer_id}`.toLowerCase().includes(query.toLowerCase()));
  const ranked = [...visible].sort((a, b) => {
    const left = byId.get(a.customer_id)?.exposure_proxy;
    const right = byId.get(b.customer_id)?.exposure_proxy;
    if (!left && !right) return a.created_at.localeCompare(b.created_at);
    if (!left) return 1;
    if (!right) return -1;
    if (left.currency !== right.currency) return left.currency.localeCompare(right.currency);
    return right.amount_minor - left.amount_minor;
  });
  const activeCase = (item: DecisionCase) => ['PROPOSED', 'HUMAN_REVIEWED', 'ASSIGNED', 'EXECUTED', 'FOLLOW_UP_DUE', 'DEFERRED'].includes(item.status);
  const assigned = cases.filter(item => item.owner != null && activeCase(item)).length;
  const unassigned = cases.filter(item => item.owner == null && activeCase(item)).length;
  const queuedForReview = cases.filter(item => ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)).length;
  const clearFilterQuery = () => setRoute('PRIORITY_REVIEW');

  return <>
    <div className="notice ambernote">Browser-only workflow simulation. Decisions, budget checks, capacity, and audit entries are not authenticated or persisted; no customer communication is sent. Changes reset on reload.</div>
    <div className="page-tabs" role="tablist" aria-label="Retention Actions views"><button role="tab" aria-selected={mainTab === 'queue'} onClick={() => setMainTab('queue')}>Work Queue <span>{queuedForReview} awaiting review</span></button><button role="tab" aria-selected={mainTab === 'strategy'} onClick={() => setMainTab('strategy')}>Strategy &amp; ROI Simulator <span>Scenario only</span></button></div>

    {mainTab === 'queue' ? <>
      <section className="metrics capacity-metrics" aria-label="Review capacity and workload"><article className="quick"><small>Review capacity</small><strong>{capacity.review_slots - capacity.used_review_slots} / {capacity.review_slots}</strong><span>Available slots / total</span></article><article className="quick"><small>Awaiting review</small><strong>{capacity.pending}</strong><span>Proposed, human reviewed or deferred</span></article><article className="quick alert"><small>Overdue cases</small><strong>{capacity.overdue ?? 'N/A'}</strong><span>{capacity.overdue == null ? 'No authorized as-of cutoff' : 'At fixture cutoff'}</span></article><article className="quick"><small>Assigned workload</small><strong>{assigned}</strong><span>{unassigned} open cases unassigned</span></article><article className="quick"><small>Staff minutes remaining</small><strong>{Math.max(0, capacity.staff_minutes_total - capacity.staff_minutes_used)}</strong><span>Of {capacity.staff_minutes_total} demo minutes</span></article><article className="quick"><small>Investigation queue</small><strong>{capacity.investigation_queue}</strong><span>Human review route</span></article></section>
      <section className="card"><div className="section-head"><div><h2>Budget by currency</h2><p className="muted">Fixture capacity values; actual budget authority is not connected.</p></div></div><div className="budget-grid">{capacity.budgets.map(limit => { const used = capacity.budget_used.find(value => value.currency === limit.currency)?.amount_minor ?? 0; return <div key={limit.currency}><small>{limit.currency} · demo allocation</small><b>{formatMoney({ amount_minor: Math.max(0, limit.amount_minor - used), currency: limit.currency })} remaining</b><span>{formatMoney({ amount_minor: used, currency: limit.currency })} allocated / {formatMoney(limit)} total</span></div>; })}</div></section>
      <section className="card stage-section"><div className="section-head"><div><h2>Prioritized work queue</h2><p className="muted">Route tabs follow the current decision-engine contract. Within a route, cases are ordered by currency then same-currency exposure proxy.</p></div><span className="pill neutral">{ranked.length} shown</span></div><div className="case-tabs route-tabs" role="tablist" aria-label="Decision routes">{routes.map(value => { const routeCases = cases.filter(item => item.route === value); const awaiting = routeCases.filter(item => ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)).length; return <button key={value} type="button" role="tab" aria-selected={route === value} onClick={() => setRoute(value)}>{routeLabel(value)} <b>{routeCases.length}</b><small>{awaiting} awaiting</small></button>; })}</div><div className="filters"><input aria-label="Search retention cases" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search account or case ID"/><button className="btn outline" onClick={() => { setQuery(''); clearFilterQuery(); }}>Clear search</button></div>{ranked.length ? <div className="tablewrap"><table><thead><tr><th>Account / case</th><th>Risk · 7d / 30d</th><th>Evidence status</th><th>MRR / exposure</th><th>Supporting evidence</th><th>Route / recommendation</th><th>Owner / due</th><th>Status</th><th>Open</th></tr></thead><tbody>{ranked.map((item, index) => { const account = byId.get(item.customer_id)!; const recommendation = item.proposed_action ? routeLabel(item.proposed_action) : 'No action proposed'; return <tr key={item.id}><td><b>#{index + 1} · {account.customer_id}</b><small>{item.id} · {account.segment ?? 'Segment unavailable'}</small></td><td>{formatRisk(account.prediction, 7)} / {formatRisk(account.prediction, 30)}</td><td><EvidencePills reliability={account.prediction?.reliability.status} freshness={account.prediction?.data_freshness.status}/></td><td>{formatMoney(account.mrr)}<small>At-risk proxy: {formatMoney(account.exposure_proxy)}</small></td><td>{item.fact_ids.length} fact(s)<small>{item.warnings.length ? `${item.warnings.length} warning(s)` : 'No listed warnings'}</small></td><td>{routeLabel(item.route)}<small>Recommend: {recommendation}</small></td><td>{item.owner ?? 'Unassigned'}<small>{formatDateTime(item.due_at)}</small></td><td><span className="pill neutral">{routeLabel(item.status)}</span></td><td><button className="btn outline table-action" onClick={() => navigate(casePath(item.id))}>Open Retention Actions case</button></td></tr>; })}</tbody></table></div> : <p className="empty-trend">No cases match this route, shared search, and currency filters.</p>}<p className="caption">Exposure proxy is probability × MRR, not expected saved revenue. Missing score, evidence or valuation is not treated as zero.</p></section>
    </> : <StrategyRoiSimulator accounts={accounts.rows} cases={cases} capacity={capacity} />}
  </>;
}
