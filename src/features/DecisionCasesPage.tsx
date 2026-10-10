import { useState } from 'react';
import { useApp } from '../app/AppContext';
import { casePath } from '../app/routes';
import type { AccountRecord, Currency, Route } from '../domain/customer';
import type { DecisionCase } from '../domain/decision';
import { calculateScenario } from '../domain/scenario';
import { formatDateTime, formatMoney, formatRisk, majorToMinor, minorToMajor } from '../domain/format';
import { useCustomers } from '../hooks/useCustomers';
import { useDecisionCases } from '../hooks/useDecisionCases';
import { proposalsFor } from '../services/decisionService';
import { EvidencePills } from '../components/StatusPills';

const routes: Route[] = ['PRIORITY_REVIEW', 'HUMAN_REVIEW', 'OBSERVE', 'KNOWN_CANCELLATION', 'NOT_ELIGIBLE'];
const routeLabel = (value: string) => value.replaceAll('_', ' ').toLowerCase();
type MainTab = 'queue' | 'strategy';
type Strategy = 'exposure' | 'risk';
type Candidate = { item: DecisionCase; account: AccountRecord; action: ReturnType<typeof proposalsFor>[number] };

export function DecisionCasesPage() {
  const { navigate, query, setQuery, currency } = useApp();
  const { cases, capacity, status, error } = useDecisionCases();
  const accounts = useCustomers();
  const [mainTab, setMainTab] = useState<MainTab>('queue');
  const [route, setRoute] = useState<Route>('PRIORITY_REVIEW');
  const [scenarioCurrency, setScenarioCurrency] = useState<Currency>('MYR');
  const [scenarioBudget, setScenarioBudget] = useState(500);
  const [scenarioCapacity, setScenarioCapacity] = useState(4);
  const [strategy, setStrategy] = useState<Strategy>('exposure');
  const [scenarioCaseId, setScenarioCaseId] = useState('');
  const [scenarioActionId, setScenarioActionId] = useState('');
  const [margin, setMargin] = useState(70);
  const [assumedReduction, setAssumedReduction] = useState(10);

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
  const candidates: Candidate[] = cases.flatMap(item => {
    const account = byId.get(item.customer_id);
    if (!account || !['PRIORITY_REVIEW', 'HUMAN_REVIEW'].includes(item.route) || !['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)) return [];
    const probability = account.prediction?.status === 'scored' ? account.prediction.p_churn_30d : null;
    if (probability == null) return [];
    const action = proposalsFor(item).find(proposal => proposal.eligible && proposal.id !== 'NO_INTERVENTION' && proposal.estimated_cost?.currency === scenarioCurrency);
    return action ? [{ item, account, action }] : [];
  });
  const scenarioCandidates = strategy === 'exposure' ? candidates.filter(candidate => candidate.account.exposure_proxy?.currency === scenarioCurrency) : candidates;
  const sortedCandidates = [...scenarioCandidates].sort((a, b) => {
    const left = strategy === 'risk' ? a.account.prediction?.p_churn_30d ?? -1 : a.account.exposure_proxy?.currency === scenarioCurrency ? a.account.exposure_proxy.amount_minor : -1;
    const right = strategy === 'risk' ? b.account.prediction?.p_churn_30d ?? -1 : b.account.exposure_proxy?.currency === scenarioCurrency ? b.account.exposure_proxy.amount_minor : -1;
    return right - left;
  });
  const scenarioBudgetMinor = majorToMinor(scenarioBudget, scenarioCurrency) ?? 0;
  let budgetRemaining = scenarioBudgetMinor;
  const scenarioAllocated: Candidate[] = [];
  for (const candidate of sortedCandidates) {
    if (scenarioAllocated.length >= scenarioCapacity) break;
    const cost = candidate.action.estimated_cost?.amount_minor;
    if (cost == null || cost > budgetRemaining) continue;
    scenarioAllocated.push(candidate);
    budgetRemaining -= cost;
  }
  const scenarioSpent = scenarioBudgetMinor - budgetRemaining;
  const eligibleRoiCases = cases.filter(item => {
    const account = byId.get(item.customer_id);
    return Boolean(account?.mrr && account.prediction?.p_churn_30d != null && proposalsFor(item).some(action => action.eligible && action.estimated_cost?.currency === account.mrr?.currency));
  });
  const roiCase = eligibleRoiCases.find(item => item.id === scenarioCaseId) ?? eligibleRoiCases[0];
  const roiAccount = roiCase ? byId.get(roiCase.customer_id) : undefined;
  const roiActions = roiCase ? proposalsFor(roiCase).filter(action => action.eligible && action.id !== 'NO_INTERVENTION' && action.estimated_cost?.currency === roiAccount?.mrr?.currency) : [];
  const roiAction = roiActions.find(action => action.id === scenarioActionId) ?? roiActions.find(action => action.id === roiCase?.proposed_action) ?? roiActions[0];
  const roiMrr = roiAccount ? minorToMajor(roiAccount.mrr) : null;
  const roiCost = roiAction ? minorToMajor(roiAction.estimated_cost) : null;
  const roiResult = roiCase && roiMrr != null && roiAccount?.prediction?.p_churn_30d != null && roiCost != null ? calculateScenario({ mrr: roiMrr, p30: roiAccount.prediction.p_churn_30d, margin: margin / 100, cost: roiCost, assumed_reduction: assumedReduction / 100 }) : null;
  const clearFilterQuery = () => setRoute('PRIORITY_REVIEW');

  return <>
    <div className="notice ambernote">Browser-only workflow simulation. Decisions, budget checks, capacity, and audit entries are not authenticated or persisted; no customer communication is sent. Changes reset on reload.</div>
    <div className="page-tabs" role="tablist" aria-label="Retention Actions views"><button role="tab" aria-selected={mainTab === 'queue'} onClick={() => setMainTab('queue')}>Work Queue <span>{queuedForReview} awaiting review</span></button><button role="tab" aria-selected={mainTab === 'strategy'} onClick={() => setMainTab('strategy')}>Strategy &amp; ROI <span>Scenario only</span></button></div>

    {mainTab === 'queue' ? <>
      <section className="metrics capacity-metrics" aria-label="Review capacity and workload"><article className="quick"><small>Review capacity</small><strong>{capacity.review_slots - capacity.used_review_slots} / {capacity.review_slots}</strong><span>Available slots / total</span></article><article className="quick"><small>Awaiting review</small><strong>{capacity.pending}</strong><span>Proposed, human reviewed or deferred</span></article><article className="quick alert"><small>Overdue cases</small><strong>{capacity.overdue ?? 'N/A'}</strong><span>{capacity.overdue == null ? 'No authorized as-of cutoff' : 'At fixture cutoff'}</span></article><article className="quick"><small>Assigned workload</small><strong>{assigned}</strong><span>{unassigned} open cases unassigned</span></article><article className="quick"><small>Staff minutes remaining</small><strong>{Math.max(0, capacity.staff_minutes_total - capacity.staff_minutes_used)}</strong><span>Of {capacity.staff_minutes_total} demo minutes</span></article><article className="quick"><small>Investigation queue</small><strong>{capacity.investigation_queue}</strong><span>Human review route</span></article></section>
      <section className="card"><div className="section-head"><div><h2>Budget by currency</h2><p className="muted">Fixture capacity values; actual budget authority is not connected.</p></div></div><div className="budget-grid">{capacity.budgets.map(limit => { const used = capacity.budget_used.find(value => value.currency === limit.currency)?.amount_minor ?? 0; return <div key={limit.currency}><small>{limit.currency} · demo allocation</small><b>{formatMoney({ amount_minor: Math.max(0, limit.amount_minor - used), currency: limit.currency })} remaining</b><span>{formatMoney({ amount_minor: used, currency: limit.currency })} allocated / {formatMoney(limit)} total</span></div>; })}</div></section>
      <section className="card stage-section"><div className="section-head"><div><h2>Prioritized work queue</h2><p className="muted">Route tabs follow the current decision-engine contract. Within a route, cases are ordered by currency then same-currency exposure proxy.</p></div><span className="pill neutral">{ranked.length} shown</span></div><div className="case-tabs route-tabs" role="tablist" aria-label="Decision routes">{routes.map(value => { const routeCases = cases.filter(item => item.route === value); const awaiting = routeCases.filter(item => ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)).length; return <button key={value} type="button" role="tab" aria-selected={route === value} onClick={() => setRoute(value)}>{routeLabel(value)} <b>{routeCases.length}</b><small>{awaiting} awaiting</small></button>; })}</div><div className="filters"><input aria-label="Search retention cases" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search account or case ID"/><button className="btn outline" onClick={() => { setQuery(''); clearFilterQuery(); }}>Clear search</button></div>{ranked.length ? <div className="tablewrap"><table><thead><tr><th>Account / case</th><th>Risk · 7d / 30d</th><th>Evidence status</th><th>MRR / exposure</th><th>Supporting evidence</th><th>Route / recommendation</th><th>Owner / due</th><th>Status</th><th>Open</th></tr></thead><tbody>{ranked.map((item, index) => { const account = byId.get(item.customer_id)!; const recommendation = item.proposed_action ? routeLabel(item.proposed_action) : 'No action proposed'; return <tr key={item.id}><td><b>#{index + 1} · {account.customer_id}</b><small>{item.id} · {account.segment ?? 'Segment unavailable'}</small></td><td>{formatRisk(account.prediction, 7)} / {formatRisk(account.prediction, 30)}</td><td><EvidencePills reliability={account.prediction?.reliability.status} freshness={account.prediction?.data_freshness.status}/></td><td>{formatMoney(account.mrr)}<small>At-risk proxy: {formatMoney(account.exposure_proxy)}</small></td><td>{item.fact_ids.length} fact(s)<small>{item.warnings.length ? `${item.warnings.length} warning(s)` : 'No listed warnings'}</small></td><td>{routeLabel(item.route)}<small>Recommend: {recommendation}</small></td><td>{item.owner ?? 'Unassigned'}<small>{formatDateTime(item.due_at)}</small></td><td><span className="pill neutral">{routeLabel(item.status)}</span></td><td><button className="btn outline table-action" onClick={() => navigate(casePath(item.id))}>Open Retention Actions case</button></td></tr>; })}</tbody></table></div> : <p className="empty-trend">No cases match this route, shared search, and currency filters.</p>}<p className="caption">Exposure proxy is probability × MRR, not expected saved revenue. Missing score, evidence or valuation is not treated as zero.</p></section>
    </> : <>
      <section className="card scenario-workbench"><div className="section-head"><div><span className="pill amber">SCENARIO ONLY</span><h2>Budget &amp; capacity what-if</h2><p className="muted">This estimates how many currently eligible, scored review cases fit a hypothetical budget. It does not commit funds or change live case priority.</p></div></div><div className="form-grid"><label>Scenario currency<select value={scenarioCurrency} onChange={event => setScenarioCurrency(event.target.value as Currency)}>{capacity.budgets.map(value => <option key={value.currency} value={value.currency}>{value.currency}</option>)}</select></label><label>Scenario budget ({scenarioCurrency})<input type="number" min="0" step="100" value={scenarioBudget} onChange={event => setScenarioBudget(Math.max(0, Number(event.target.value)))}/></label><label>Available review capacity<input type="number" min="0" max="50" step="1" value={scenarioCapacity} onChange={event => setScenarioCapacity(Math.min(50, Math.max(0, Number(event.target.value))))}/></label><label>Prioritization heuristic<select value={strategy} onChange={event => setStrategy(event.target.value as Strategy)}><option value="exposure">Highest exposure proxy (same currency)</option><option value="risk">Highest p30 probability</option></select></label></div><div className="scenario-results"><div><small>Eligible scored cases</small><b>{scenarioCandidates.length}</b></div><div><small>Allocated in scenario</small><b>{scenarioAllocated.length}</b></div><div><small>Estimated allocation</small><b>{formatMoney({ amount_minor: scenarioSpent, currency: scenarioCurrency })}</b></div><div><small>Unallocated scenario budget</small><b>{formatMoney({ amount_minor: budgetRemaining, currency: scenarioCurrency })}</b></div></div><div className="tablewrap"><table><thead><tr><th>Scenario rank</th><th>Account / case</th><th>p30</th><th>At-risk exposure</th><th>Eligible proposal</th><th>Estimated cost</th><th>Scenario allocation</th></tr></thead><tbody>{sortedCandidates.slice(0, 8).map((candidate, index) => <tr key={candidate.item.id}><td>#{index + 1}</td><td>{candidate.account.customer_id}<small>{candidate.item.id}</small></td><td>{formatRisk(candidate.account.prediction, 30)}</td><td>{formatMoney(candidate.account.exposure_proxy)}</td><td>{routeLabel(candidate.action.id)}</td><td>{formatMoney(candidate.action.estimated_cost)}</td><td>{scenarioAllocated.includes(candidate) ? 'Included' : 'Not allocated'}</td></tr>)}</tbody></table></div><p className="caption">Candidates require an eligible demo proposal, p30 score, and cost in the selected currency. The exposure heuristic excludes candidates without same-currency exposure; these are fixture estimates, not evaluated policy results.</p></section>
      <section className="card stage-section"><div className="section-head"><div><h2>Strategy comparison</h2><p className="muted">Revenue Captured @K and comparative performance need valid historical replay and mature source-backed outcomes.</p></div><span className="pill neutral">Unavailable</span></div><p className="empty-trend">No historical replay or mature outcome labels are connected. The what-if heuristics above are not evaluated strategies and make no performance claim.</p></section>
      <section className="card stage-section"><span className="pill amber">SCENARIO ONLY</span><h2 className="subheading">Break-even retention scenario</h2><p className="muted">Assumed improvement is a scenario input, not measured effectiveness or causal uplift.</p>{eligibleRoiCases.length === 0 ? <p className="empty-trend">Unavailable — no case has a valid MRR, p30 and eligible action cost in this fixture.</p> : <><div className="form-grid"><label>Case<select value={roiCase?.id ?? ''} onChange={event => { setScenarioCaseId(event.target.value); setScenarioActionId(''); }}><option value="">Select case</option>{eligibleRoiCases.map(item => <option key={item.id} value={item.id}>{byId.get(item.customer_id)?.customer_id} · {item.id}</option>)}</select></label><label>Eligible action<select value={roiAction?.id ?? ''} onChange={event => setScenarioActionId(event.target.value)}>{roiActions.map(action => <option key={action.id} value={action.id}>{routeLabel(action.id)} · {formatMoney(action.estimated_cost)}</option>)}</select></label><label>Contribution margin (%)<input type="number" min="0" max="100" value={margin} onChange={event => setMargin(Math.min(100, Math.max(0, Number(event.target.value))))}/></label><label>Assumed absolute churn reduction (percentage points)<input type="number" min="0" max="100" value={assumedReduction} onChange={event => setAssumedReduction(Math.min(100, Math.max(0, Number(event.target.value))))}/></label></div>{roiResult && roiAccount?.mrr ? <div className="values scenario-results-detail"><p><span>Action cost · {roiAccount.mrr.currency}</span><b>{formatMoney(roiAction?.estimated_cost ?? null)}</b></p><p><span>Baseline p30 risk</span><b>{formatRisk(roiAccount.prediction, 30)}</b></p><p><span>Scenario expected retained value</span><b>{formatMoney({ amount_minor: majorToMinor(roiResult.gross_value, roiAccount.mrr.currency, { allowNegative: true }) ?? 0, currency: roiAccount.mrr.currency }, { allowNegative: true })}</b></p><p><span>Scenario net value</span><b>{formatMoney({ amount_minor: majorToMinor(roiResult.net_value, roiAccount.mrr.currency, { allowNegative: true }) ?? 0, currency: roiAccount.mrr.currency }, { allowNegative: true })}</b></p><p><span>Break-even retention improvement</span><b>{(roiResult.break_even_reduction * 100).toFixed(2)} percentage points</b></p><p><span>Scenario ROI</span><b>{(roiResult.roi * 100).toFixed(1)}%</b></p>{roiResult.impossible && <p className="scenario-warning">Break-even improvement exceeds this account’s baseline p30 risk.</p>}</div> : <p className="empty-trend">Unavailable — the selected case needs valid MRR, p30 and action-cost inputs.</p>}<p className="caption">Scenario values are arithmetic under user-entered assumptions. They are not actual retained revenue, observed savings or measured ROI.</p></>}</section>
    </>}
  </>;
}
