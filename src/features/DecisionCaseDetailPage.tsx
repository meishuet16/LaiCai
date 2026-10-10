import { useEffect, useState } from 'react';
import { useApp } from '../app/AppContext';
import { predictionPath, timelinePath } from '../app/routes';
import type { ActionId, DecisionKind } from '../domain/decision';
import { formatDateTime, formatMoney, formatRisk, majorToMinor, minorToMajor } from '../domain/format';
import { calculateScenario } from '../domain/scenario';
import { useAccount } from '../hooks/useAccount';
import { useDecisionCase } from '../hooks/useDecisionCases';
import { useTimeline } from '../hooks/useTimeline';
import { decisionDataSource, proposalsFor } from '../services/decisionService';
import { EvidencePills } from '../components/StatusPills';

const label = (value: string) => value.replaceAll('_', ' ').toLowerCase();
const pct = (value: number) => `${(value * 100).toFixed(2)}%`;
const pp = (value: number) => `${(value * 100).toFixed(2)} pp`;

export function DecisionCaseDetailPage({ caseId }: { caseId: string }) {
  const { navigate, role, dataMode } = useApp();
  const { item, status, error, refresh } = useDecisionCase(caseId);
  const account = useAccount(item?.customer_id ?? '');
  const customerTimeline = useTimeline(item?.customer_id ?? '');
  const [kind, setKind] = useState<DecisionKind>('APPROVE');
  const [actionId, setActionId] = useState<ActionId | ''>('');
  const [reason, setReason] = useState('');
  const [dueAt, setDueAt] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState('');
  const [outcome, setOutcome] = useState<'EXECUTED' | 'CANCELLED' | 'FAILED'>('EXECUTED');
  const [actualCost, setActualCost] = useState('');
  const [actualMinutes, setActualMinutes] = useState('');
  const [executionReason, setExecutionReason] = useState('');
  const [followUp, setFollowUp] = useState('');
  const [followUpNote, setFollowUpNote] = useState('');
  const [margin, setMargin] = useState('70');
  const [assumedReduction, setAssumedReduction] = useState('10');
  useEffect(() => { if (item) setActionId(item.proposed_action ?? ''); }, [item?.id]);
  if (status === 'loading' || account.status === 'loading') return <p role="status">Loading case…</p>;
  if (status === 'unavailable' || account.status === 'unavailable') return <section className="card unavailable-state"><h2>Decision details are not connected</h2><p>{error ?? account.error ?? 'Decision-case read and approval APIs are unavailable.'}</p></section>;
  if (status === 'error' || !item) return <div role="alert" className="notice ambernote">{error ?? 'Case not found.'}</div>;
  const customer = account.account;
  if (!customer) return <div role="alert" className="notice ambernote">Account not found.</div>;
  const proposals = proposalsFor(item);
  const relatedEvents = customerTimeline.record?.events.filter(event => event.case_id === item.id || event.fact_ids.some(factId => item.fact_ids.includes(factId))).slice(0, 5) ?? [];
  const action = proposals.find(value => value.id === actionId);
  const approving = kind === 'APPROVE' || kind === 'MODIFY';
  const canDecide = ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status);
  const cost = action?.estimated_cost ?? item.estimated_cost;
  const result = calculateScenario({ mrr: minorToMajor(customer.mrr), p30: customer.prediction?.p_churn_30d ?? null, margin: Number(margin) / 100, cost: minorToMajor(cost) ?? 0, assumed_reduction: Number(assumedReduction) / 100 });
  const submitDecision = async () => {
    try {
      await decisionDataSource(dataMode).recordDecision(item.id, { kind, action_id: approving ? actionId || null : null, reason, due_at: (kind === 'DEFER' || approving) && dueAt ? `${dueAt}T12:00:00Z` : null, actor: role }, role);
      setMessage('Decision recorded in the case audit history.'); setConfirming(false); setReason(''); void refresh();
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Decision could not be recorded.'); setConfirming(false); }
  };
  const submitExecution = async () => {
    try {
      const currency = item.estimated_cost?.currency;
      const actualCostMinor = currency && actualCost !== '' ? majorToMinor(Number(actualCost), currency) : null;
      await decisionDataSource(dataMode).recordExecution(item.id, { outcome, reason: executionReason, actual_cost: actualCostMinor == null || !currency ? null : { amount_minor: actualCostMinor, currency }, actual_minutes: actualMinutes === '' ? null : Number(actualMinutes), follow_up_at: outcome === 'EXECUTED' && followUp ? `${followUp}T12:00:00Z` : null, actor: role }, role);
      setMessage('Execution evidence recorded in the case audit history.'); setExecutionReason(''); void refresh();
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Execution could not be recorded.'); }
  };
  return <>
    <div className="notice bluenote">Human-governed workflow · Approval records a task assignment; external outreach or payment actions require their connected operating system.</div>
    {message && <div className="notice bluenote" role="status">{message}</div>}
    <div className="detail-title"><div><h2>{customer.name ?? customer.customer_id}</h2><p className="muted">{item.id} · {customer.customer_id} · {customer.segment ?? 'Segment unavailable'} · {customer.plan ?? 'Plan unavailable'}</p></div><span className="pill neutral">{label(item.status)}</span></div>
    <div className="case-detail-layout"><div className="case-main">
      <section className="card"><h2>At a glance</h2><div className="case-facts"><div><small>Risk · 7d / 30d</small><b>{formatRisk(customer.prediction, 7)} / {formatRisk(customer.prediction, 30)}</b></div><div><small>MRR / exposure proxy</small><b>{formatMoney(customer.mrr)} / {formatMoney(customer.exposure_proxy)}</b></div><div><small>Route</small><b>{label(item.route)}</b></div><div><small>Due</small><b>{formatDateTime(item.due_at)}</b></div><div><small>Evidence quality</small><EvidencePills reliability={customer.prediction?.reliability.status} freshness={customer.prediction?.data_freshness.status}/></div><div><small>Model / cutoff</small><b>{customer.prediction?.model_version ?? 'N/A'} / {formatDateTime(customer.prediction?.as_of ?? null)}</b></div></div><p className="caption">Why routed: {item.route_reason}. Evidence supports review priority; it is not a causal finding.</p><button className="tablelink" onClick={() => customer.prediction && navigate(predictionPath(customer.prediction.prediction_id))}>Prediction details</button><button className="tablelink" onClick={() => navigate(timelinePath(customer.customer_id))}>Customer Insights</button></section>
      <details className="card stage-section case-disclosure"><summary><span>Evidence & safeguards</span><small>{item.fact_ids.length} facts · {relatedEvents.length} related events</small></summary><p className="caption">Fact IDs link the case to its persisted prediction and evidence record.</p><ul className="plain-list">{item.facts.map((fact, index) => <li key={item.fact_ids[index] ?? fact}><b>{item.fact_ids[index] ?? 'No fact ID'}</b> — {fact}</li>)}</ul><h3>Related customer events</h3>{customerTimeline.status === 'error' ? <p className="empty-trend">Related events unavailable.</p> : relatedEvents.length ? <ul className="plain-list">{relatedEvents.map(event => <li key={event.id}><b>{event.title}</b> · {formatDateTime(event.available_at)}<br/>{event.summary}</li>)}</ul> : <p className="empty-trend">{customerTimeline.status === 'loading' ? 'Loading related events…' : 'No related events available.'}</p>}<p className="caption">Freshness: {customer.prediction?.data_freshness.status ?? 'unknown'} · {item.selected_action ? 'Action already recorded; check cooldown before repeating.' : 'No active action recorded.'}</p>{item.warnings.map(warning => <div className="notice ambernote" key={warning}>{warning}</div>)}</details>
      <details className="card stage-section case-disclosure"><summary><span>Action proposals</span><small>{proposals.filter(proposal => proposal.eligible).length} eligible</small></summary><p className="caption">Eligible actions create governed tasks with owner, capacity, cost and audit controls.</p><div className="proposal-list">{proposals.map(proposal => <article className="proposal" key={proposal.id}><div className="section-head"><div><b>{label(proposal.id)}</b><p>{proposal.description}</p></div><span className={`pill ${proposal.eligible ? '' : 'neutral'}`}>{proposal.availability === 'demo_operational' ? 'available' : proposal.availability.replaceAll('_', ' ')}</span></div><small>Eligibility: {proposal.eligible ? 'Eligible' : `Unavailable — ${proposal.contraindication}`} · Facts: {proposal.fact_ids.join(', ') || 'none'}</small><small>Estimated: {formatMoney(proposal.estimated_cost)} · {proposal.estimated_minutes} staff min · Approval: {proposal.approval_role} · Cooldown: {proposal.cooldown}</small></article>)}</div></details>
      {canDecide && <section className="card stage-section"><h2>Human decision</h2><p className="muted">Manager role required. A reason is mandatory and every change is persisted to the case audit history.</p><div className="form-grid"><label>Decision<select value={kind} onChange={event => { setKind(event.target.value as DecisionKind); setConfirming(false); }}><option value="APPROVE">Approve proposal</option><option value="MODIFY">Modify proposal</option><option value="REJECT">Reject</option><option value="NO_INTERVENTION">No intervention</option><option value="DEFER">Defer</option></select></label>{approving && <label>Action<select value={actionId} onChange={event => setActionId(event.target.value as ActionId)}><option value="">Select action</option>{proposals.filter(value => value.eligible && value.id !== 'NO_INTERVENTION').map(value => <option value={value.id} key={value.id}>{label(value.id)}</option>)}</select></label>}{(approving || kind === 'DEFER') && <label>Due date<input type="date" value={dueAt} onChange={event => setDueAt(event.target.value)}/></label>}<label className="full-width">Required reason<textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} placeholder="Document why this decision is appropriate"/></label></div>{confirming ? <div className="confirmation"><b>Confirm {label(kind)}?</b><p>Action: {approving ? label(actionId || 'none') : 'none'} · Estimated cost: {approving ? formatMoney(action?.estimated_cost ?? null) : 'N/A'} · Staff effort: {approving ? action?.estimated_minutes ?? 0 : 0} min · Review slot: {approving ? '1 if newly approved' : '0'}</p><button className="btn" onClick={() => void submitDecision()}>Confirm decision</button><button className="btn outline" onClick={() => setConfirming(false)}>Cancel</button></div> : <button className="btn" disabled={role !== 'Manager' || !reason.trim() || (approving && !action?.eligible) || (kind === 'DEFER' && !dueAt)} onClick={() => setConfirming(true)}>Review budget and confirm</button>}</section>}
      {item.status === 'ASSIGNED' && <section className="card stage-section"><h2>Record execution</h2><p className="muted">Record completion evidence, actual cost, staff effort and the next follow-up date.</p><div className="form-grid"><label>Outcome<select value={outcome} onChange={event => setOutcome(event.target.value as typeof outcome)}><option value="EXECUTED">Executed</option><option value="CANCELLED">Cancelled</option><option value="FAILED">Failed</option></select></label><label>Actual cost ({item.estimated_cost?.currency ?? 'currency'})<input type="number" min="0" step="0.01" value={actualCost} onChange={event => setActualCost(event.target.value)} placeholder="Unknown if blank"/></label><label>Actual staff minutes<input type="number" min="0" step="1" value={actualMinutes} onChange={event => setActualMinutes(event.target.value)} placeholder="Unknown if blank"/></label><label>Follow-up due<input type="date" value={followUp} onChange={event => setFollowUp(event.target.value)} disabled={outcome !== 'EXECUTED'}/></label><label className="full-width">Required execution note<textarea rows={3} value={executionReason} onChange={event => setExecutionReason(event.target.value)}/></label></div><button className="btn" disabled={!['Manager', 'CSM'].includes(role) || !executionReason.trim()} onClick={() => void submitExecution()}>Record execution</button></section>}
      {['EXECUTED', 'FOLLOW_UP_DUE'].includes(item.status) && <section className="card stage-section"><h2>Record follow-up</h2><p className="muted">Due: {formatDateTime(item.follow_up_at)}. Record what the team observed, without attributing retention to the action.</p><label className="full-width">Required follow-up note<textarea rows={3} value={followUpNote} onChange={event => setFollowUpNote(event.target.value)}/></label><button className="btn" disabled={!['Manager', 'CSM'].includes(role) || !followUpNote.trim()} onClick={async () => { try { await decisionDataSource(dataMode).recordFollowUp(item.id, followUpNote, role, role); setMessage('Follow-up recorded in the case audit history.'); setFollowUpNote(''); void refresh(); } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Follow-up could not be recorded.'); } }}>Record follow-up</button></section>}
    </div><div className="case-side">
      <details className="card case-disclosure"><summary><span>Break-even ROI</span><small>SCENARIO ONLY</small></summary><p className="caption">One-month assumptions, not measured savings.</p><div className="values"><p><span>MRR</span><b>{formatMoney(customer.mrr)}</b></p><p><span>p30</span><b>{formatRisk(customer.prediction, 30)}</b></p><p><span>Estimated action cost</span><b>{formatMoney(cost ?? null)}</b></p></div><div className="form-grid scenario-inputs"><label>Contribution margin (%)<input type="number" min="0" max="100" value={margin} onChange={event => setMargin(event.target.value)}/></label><label>Assumed absolute reduction (pp)<input type="number" min="0" max="100" value={assumedReduction} onChange={event => setAssumedReduction(event.target.value)}/></label></div>{result ? <div className="values"><p><span>Break-even absolute reduction</span><b>{pp(result.break_even_reduction)}</b></p><p><span>Share of baseline risk</span><b>{pct(result.break_even_share)}</b></p><p><span>Scenario gross value</span><b>{formatMoney({ amount_minor: majorToMinor(result.gross_value, customer.mrr!.currency, { allowNegative: true }) ?? 0, currency: customer.mrr!.currency }, { allowNegative: true })}</b></p><p><span>Scenario net value</span><b>{formatMoney({ amount_minor: majorToMinor(result.net_value, customer.mrr!.currency, { allowNegative: true }) ?? 0, currency: customer.mrr!.currency }, { allowNegative: true })}</b></p><p><span>Scenario ROI</span><b>{pct(result.roi)}</b></p>{result.impossible && <p className="scenario-warning">Break-even exceeds baseline p30; impossible under this one-month scenario.</p>}</div> : <p className="empty-trend">Unavailable — valid MRR, p30, cost, margin and reduction are required.</p>}<p className="caption">Assumption-based estimate; no causal effect inferred.</p></details>
      <details className="card stage-section case-disclosure"><summary><span>Audit history</span><small>{item.audit.length} entries</small></summary><p className="caption">Persisted routing, decision, execution and follow-up history.</p><ol className="audit-list">{[...item.audit].reverse().map(entry => <li key={entry.id}><b>{label(entry.type)}</b><small>{formatDateTime(entry.at)} · {entry.actor} · {entry.id}</small><p>{entry.detail}</p></li>)}</ol></details>
      <details className="card stage-section case-disclosure"><summary><span>Outcome feedback</span><small>Tracked by horizon</small></summary><p className="empty-trend">Outcome windows and reconciliation state are monitored in Learning & Model Health. Observed retention is never attributed to an action without causal evidence.</p><button className="tablelink" onClick={() => navigate('/learning')}>Learning & Model Health</button></details>
    </div></div>
  </>;
}
