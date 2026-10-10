import { useEffect, useRef, useState } from 'react';
import { useApp } from '../app/AppContext';
import { casePath, predictionPath } from '../app/routes';
import type { Horizon } from '../domain/customer';
import { formatDateTime, formatMoney, formatRisk } from '../domain/format';
import { customerLabel } from '../domain/customer';
import { feedbackAt, visibleTimelineEvents, type TimelineCategory } from '../domain/timeline';
import { useTimeline } from '../hooks/useTimeline';
import { EvidencePills, RiskPill, type RiskBand } from '../components/StatusPills';
import { CustomerSwitcher } from '../components/CustomerSwitcher';

const label = (value: string) => value.replaceAll('_', ' ').toLowerCase();
const horizons: Horizon[] = [7, 14, 30];
const toUtc = (value: string) => value ? `${value}:00Z` : null;

export function TimelinePage({ customerId }: { customerId: string }) {
  const { navigate, horizon, role } = useApp();
  const { status, record, error } = useTimeline(customerId);
  const [from, setFrom] = useState('');
  const [through, setThrough] = useState('');
  const [historicAt, setHistoricAt] = useState('');
  const [category, setCategory] = useState<TimelineCategory | 'all'>('all');
  const [eventType, setEventType] = useState('all');
  const [mode, setMode] = useState<'all' | 'decisions' | 'source'>('all');
  const [feedbackHorizon, setFeedbackHorizon] = useState<Horizon | 'all'>(horizon);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const selectedTriggerRef = useRef<HTMLButtonElement | null>(null);
  const eventDrawerRef = useRef<HTMLElement>(null);
  useEffect(() => {
    setFrom(''); setThrough(''); setHistoricAt(''); setCategory('all'); setEventType('all'); setMode('all'); setFeedbackHorizon('all'); setSelectedId(null);
  }, [customerId]);
  useEffect(() => { if (selectedId) closeButtonRef.current?.focus(); else if (selectedTriggerRef.current?.isConnected) selectedTriggerRef.current.focus(); }, [selectedId]);
  useEffect(() => {
    if (!selectedId) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setSelectedId(null); }
      if (event.key !== 'Tab') return;
      const focusable = eventDrawerRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])');
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [selectedId]);
  if (status === 'loading') return <p role="status">Loading customer timeline…</p>;
  if (status === 'unavailable') return <section className="card unavailable-state"><h2>Customer Insights is temporarily unavailable</h2><p>{error}</p><p>Check the account timeline, prediction history, decision, and feedback services.</p></section>;
  if (status === 'error') return <div role="alert" className="notice ambernote">{error}</div>;
  if (!record) return <div className="card"><h2>Customer not found</h2><p className="muted">No customer record is available for this identifier in the current dataset.</p><button className="btn outline" onClick={() => navigate('/predictions')}>Open Churn Prediction</button></div>;

  const { account, case: item } = record;
  const prediction = account.prediction;
  const cutoff = toUtc(historicAt);
  const currentViewCutoff = new Date().toISOString();
  const visible = visibleTimelineEvents(record.events, cutoff ?? currentViewCutoff);
  const filtered = visible.filter(event => {
    if (category !== 'all' && event.category !== category) return false;
    if (eventType !== 'all' && (event.canonical_event_type ?? event.title) !== eventType) return false;
    if (mode === 'decisions' && !['decision', 'action'].includes(event.category)) return false;
    if (mode === 'source' && event.category !== 'source') return false;
    if (from && event.occurred_at < toUtc(from)!) return false;
    if (through && event.occurred_at > toUtc(through)!) return false;
    return true;
  });
  const selected = selectedId ? visible.find(event => event.id === selectedId) ?? null : null;
  const predictionVisible = prediction && prediction.generated_at != null && (!cutoff || prediction.generated_at <= cutoff);
  const currentProbability = predictionVisible && prediction?.status === 'scored' ? horizon === 7 ? prediction.p_churn_7d : horizon === 14 ? prediction.p_churn_14d : prediction.p_churn_30d : null;
  const currentRiskBand: RiskBand = predictionVisible ? prediction?.risk_bands_by_horizon?.[horizon] ?? null : 'no_score';
  const feedbackRows = horizons.filter(value => feedbackHorizon === 'all' || feedbackHorizon === value).map(value => ({ horizon: value, feedback: feedbackAt(account, value, cutoff ?? currentViewCutoff) }));
  const historical = Boolean(cutoff);
  const eventTypes = [...new Set(record.events.map(event => event.canonical_event_type ?? event.title))].sort();
  return <>
    <section className="card stage-section"><div className="section-head"><div><h2>Customer profile attributes</h2><p className="muted">Source-backed fields only; unavailable attributes remain N/A.</p></div></div><div className="values"><p><span>Tenant-scoped ID</span><b>{account.tenant_id ?? 'Not supplied'}</b></p><p><span>Segment</span><b>{historical ? 'N/A — historical availability not supplied' : account.segment ?? 'N/A'}</b></p><p><span>Industry / region</span><b>{historical ? 'N/A — historical availability not supplied' : `${account.industry ?? 'N/A'} / ${account.region ?? 'N/A'}`}</b></p><p><span>Acquisition / onboarding cohort</span><b>{historical ? 'N/A — historical availability not supplied' : `${account.acquisition_channel ?? 'N/A'} / ${account.onboarding_cohort ?? 'N/A'}`}</b></p><p><span>Subscription state / plan / tenure</span><b>{historical ? 'N/A — historical availability not supplied' : `${account.subscription_state ?? 'N/A'} / ${account.plan ?? 'N/A'} / ${account.tenure_days == null ? 'N/A' : `${account.tenure_days} days`}`}</b></p><p><span>Account created</span><b>{historical ? 'N/A — historical availability not supplied' : formatDateTime(account.account_created_at)}</b></p></div></section>
    <section className="card timeline-header"><div className="section-head"><div><h2>{customerLabel(account)}</h2><p className="muted">{account.customer_id}{historical ? ' · historical profile fields require source availability timestamps' : ` · ${account.segment ?? 'Segment unavailable'} · ${account.plan ?? 'Plan unavailable'}`}</p></div><div className="customer-heading-actions"><CustomerSwitcher currentCustomerId={account.customer_id}/><span className="pill neutral">{historical ? 'KNOWN AT SELECTED TIME' : 'CURRENT WORKSPACE'}</span></div></div><div className="timeline-summary">
      <div><small>Subscription status</small><b>{historical ? 'N/A — historical status not stored' : account.subscription_state ?? 'N/A'}</b></div>
      <div><small>MRR / currency</small><b>{historical ? 'N/A — historical valuation not stored' : formatMoney(account.mrr)}</b></div>
      <div><small>Route / case</small><b>{historical ? 'N/A — historical case snapshot not stored' : `${label(item?.route ?? account.route)} / ${label(item?.status ?? 'unknown')}`}</b></div>
      <div><small>Current churn risk</small><b className="profile-risk">{predictionVisible ? `${formatRisk(prediction, horizon)} at ${horizon}d` : 'N/A — prediction not available at cutoff'} {predictionVisible && <RiskPill band={currentRiskBand}/>}</b></div>
      <div><small>Reliability / freshness</small><b>{predictionVisible ? <EvidencePills reliability={prediction.reliability.status} freshness={prediction.data_freshness.status}/> : 'N/A — prediction not available at cutoff'}</b></div>
    </div><div className="record-links">{predictionVisible && <button className="btn outline" disabled={historical} onClick={() => navigate(predictionPath(prediction!.prediction_id))}>Open Churn Prediction details</button>}{item && <button className="btn outline" disabled={historical} onClick={() => navigate(casePath(item.id))}>Open Retention Actions case</button>}</div></section>
    <section className="card stage-section"><div className="section-head"><div><h2>Current churn prediction</h2><p className="muted">Values are only shown when the prediction was available by the selected historical cutoff.</p></div><span className="pill neutral">{predictionVisible ? prediction?.model_version : 'Not known at cutoff'}</span></div><div className="probability-grid">{([7, 14, 30] as const).map(days => <article className="card probability" key={days}><span>{days}-day risk</span><strong>{predictionVisible ? formatRisk(prediction, days) : 'N/A'}</strong><small>{predictionVisible ? `Cutoff ${formatDateTime(prediction?.as_of ?? null)}` : 'Prediction generated later or unavailable'}</small></article>)}</div><div className="values"><p><span>Reliability / freshness</span><b>{predictionVisible ? <EvidencePills reliability={prediction?.reliability.status} freshness={prediction?.data_freshness.status}/> : 'N/A — prediction not available at cutoff'}</b></p><p><span>Generated</span><b>{predictionVisible ? formatDateTime(prediction?.generated_at ?? null) : 'N/A'}</b></p></div></section>
    {!historical && item && <section className="card stage-section"><h2>Current decision context</h2><p className="muted">Persisted case snapshot linked to the prediction and its supporting fact IDs.</p><div className="timeline-summary"><div><small>Route / reason</small><b>{label(item.route)} · {item.route_reason}</b></div><div><small>System proposal</small><b>{item.proposed_action ? label(item.proposed_action) : 'No action proposed'}</b></div><div><small>Human-selected action</small><b>{item.selected_action ? label(item.selected_action) : 'No action selected'}</b></div><div><small>Case due</small><b>{formatDateTime(item.due_at)}</b></div><div><small>Execution / actuals</small><b>{item.completed_at ? `${formatDateTime(item.completed_at)} · ${formatMoney(item.actual_cost)} · ${item.actual_minutes ?? 'N/A'} min` : 'Not recorded'}</b></div><div><small>Follow-up</small><b>{formatDateTime(item.follow_up_at)}</b></div></div><p className="caption">Supporting fact IDs: {item.fact_ids.join(', ') || 'N/A'}. The case view holds proposal eligibility and the available audit history.</p></section>}
    <section className="card stage-section"><div className="section-head"><div><h2>Timeline filters</h2><p className="muted">All times are UTC. “Known at this time” requires both event occurrence and system availability by the cutoff.</p></div><span className="pill neutral">{filtered.length} of {visible.length} known events</span></div><div className="timeline-filters"><label>From (occurrence)<input type="datetime-local" value={from} onChange={event => setFrom(event.target.value)}/></label><label>Through (occurrence)<input type="datetime-local" value={through} onChange={event => setThrough(event.target.value)}/></label><label>Known at this time<input type="datetime-local" max={new Date().toISOString().slice(0, 16)} value={historicAt} onChange={event => { setHistoricAt(event.target.value); setSelectedId(null); }}/></label><label>Event category<select value={category} onChange={event => setCategory(event.target.value as TimelineCategory | 'all')}><option value="all">All categories</option><option value="source">Source / data</option><option value="prediction">Prediction</option><option value="decision">Decision / audit</option><option value="action">Action / execution</option></select></label><label>Event type<select value={eventType} onChange={event => setEventType(event.target.value)}><option value="all">All event types</option>{eventTypes.map(value => <option key={value}>{value}</option>)}</select></label><label>Show<select value={mode} onChange={event => setMode(event.target.value as typeof mode)}><option value="all">All events</option><option value="decisions">Only decisions / actions</option><option value="source">Only source / data</option></select></label><label>Feedback horizon<select value={feedbackHorizon} onChange={event => setFeedbackHorizon(event.target.value === 'all' ? 'all' : Number(event.target.value) as Horizon)}><option value="all">7 / 14 / 30 days</option>{horizons.map(value => <option key={value} value={value}>{value} days</option>)}</select></label></div><button className="tablelink" onClick={() => { setFrom(''); setThrough(''); setHistoricAt(''); setCategory('all'); setEventType('all'); setMode('all'); setFeedbackHorizon('all'); setSelectedId(null); }}>Clear timeline filters</button></section>
    <div className="timeline-layout">
      <section className="card stage-section timeline-main">
        <h2>Chronological record</h2>
        <p className="muted">Order uses occurrence time; availability may be later. Select an item for exact provenance and links.</p>
        {filtered.length ? <ol className="timeline-list">{filtered.map(event => <li key={event.id}>
          <div className={`timeline-dot ${event.category}`}/>
          <button className="timeline-item" onClick={clickEvent => { selectedTriggerRef.current = clickEvent.currentTarget; setSelectedId(event.id); }}>
            <span className="timeline-item-head"><b>{event.title}</b><span className="pill neutral">{label(event.category)}</span></span>
            <small>{formatDateTime(event.occurred_at)} · available {formatDateTime(event.available_at)}</small>
            <span>{event.summary}</span>
            <small>{event.id}</small>
          </button>
        </li>)}</ol> : <p className="empty-trend">No known events match these filters. A historical cutoff never reveals later-arriving facts.</p>}
      </section>
      <section className="card stage-section timeline-side">
        <h2>Prediction feedback</h2>
        <p className="muted">Outcome windows are anchored to the prediction cutoff, not action or follow-up dates.</p>
        {feedbackRows.map(({ horizon: value, feedback }) => <div className="feedback-row" key={value}>
          <span>{value}-day outcome</span>
          <b className={`pill ${feedback?.state === 'PENDING' ? 'amber' : 'neutral'}`}>{feedback ? label(feedback.state) : 'not yet available'}</b>
          <small>{feedback?.matures_at ? `Window ends ${formatDateTime(feedback.matures_at)}` : 'No eligible prediction window'}</small>
        </div>)}
        <p className="caption">After expiry, `NOT_CONNECTED` remains until source-backed coverage and a feedback record exist; it is not a negative label, and no saved revenue is inferred.</p>
      </section>
      <div className="timeline-context-notes">
        <p><b>Evidence gaps</b> No point-in-time feature snapshot, personal baseline, historical prediction link, observed outcome, or model evaluation. Case history is not linked retroactively, and later retention is not attributed to an intervention by default.</p>
        <p><b>Data access</b> The {role} workspace view omits credentials, contact details and restricted raw payloads.</p>
      </div>
    </div>
    {selected && <div className="detail-overlay" onMouseDown={event => { if (event.target === event.currentTarget) setSelectedId(null); }}>
      <section ref={eventDrawerRef} className="card detail-panel timeline-drawer" role="dialog" aria-modal="true" aria-label="Customer event detail">
        <div className="section-head"><div><h2>{selected.title}</h2><p className="muted">Read-only synthetic event detail</p></div><button ref={closeButtonRef} className="btn outline" onClick={() => setSelectedId(null)} aria-label="Close event detail">Close</button></div>
        <div className="values"><p><span>Event ID</span><b>{selected.id}</b></p><p><span>Category / provenance</span><b>{label(selected.category)} / {label(selected.provenance)}</b></p><p><span>Occurrence</span><b>{formatDateTime(selected.occurred_at)}</b></p><p><span>Ingestion / availability</span><b>{formatDateTime(selected.available_at)}</b></p><p><span>Source</span><b>{selected.source}</b></p><p><span>Source record ID</span><b>{selected.source_record_id ?? 'N/A'}</b></p><p><span>Validation status</span><b>N/A — validator result not supplied</b></p><p><span>Policy / version</span><b>{selected.policy_version ?? 'N/A'}</b></p><p><span>Supporting fact IDs</span><b>{selected.fact_ids.join(', ') || 'N/A'}</b></p></div>
        <h2 className="subheading">Recorded context</h2><ul className="plain-list">{selected.details.map(detail => <li key={detail}>{detail}</li>)}</ul>
        <p className="caption">Permitted raw source record: N/A — no source-record endpoint is connected.</p>
        {historical && <p className="caption">Links to current records are disabled in historical view to prevent revealing later case state.</p>}
        {selected.prediction_id && <button className="tablelink" disabled={historical} onClick={() => navigate(predictionPath(selected.prediction_id!))}>Open Churn Prediction details</button>}
        {selected.case_id && <button className="tablelink" disabled={historical} onClick={() => navigate(casePath(selected.case_id!))}>Open Retention Actions case</button>}
      </section>
    </div>}
  </>;
}
