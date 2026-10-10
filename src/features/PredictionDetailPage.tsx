import { useApp } from '../app/AppContext';
import { casePath, timelinePath } from '../app/routes';
import { formatDateTime, formatMoney, formatRisk } from '../domain/format';
import { useDecisionCases } from '../hooks/useDecisionCases';
import { usePrediction } from '../hooks/usePrediction';
import { EvidencePills } from '../components/StatusPills';

export function PredictionDetailPage({ predictionId }: { predictionId: string }) {
  const { navigate } = useApp();
  const { status, account, error } = usePrediction(predictionId);
  const { cases } = useDecisionCases();
  if (status === 'loading') return <p role="status">Loading prediction…</p>;
  if (status === 'unavailable') return <section className="card unavailable-state"><h2>Prediction details are not connected</h2><p>{error}</p></section>;
  if (status === 'error') return <div role="alert" className="notice ambernote">Prediction could not be loaded.</div>;
  if (!account?.prediction) return <div className="card"><h2>Prediction not found</h2><p className="muted">It may have been removed or may not be available in this demo dataset.</p></div>;

  const prediction = account.prediction;
  const relatedCase = cases.find(item => item.customer_id === account.customer_id);
  const explanationHorizons = Object.keys(prediction.explanations_by_horizon);
  const reliabilityReasons = prediction.reliability.reasons.filter(Boolean);

  return <div className="prediction-detail-content">
    <div className="detail-title"><div><h2>{account.name ?? account.customer_id}</h2><p className="muted">Account {account.customer_id} · {account.segment ?? 'Segment unavailable'} · {account.plan ?? 'Plan unavailable'}</p></div><span className={`pill ${prediction.status === 'scored' ? 'good' : 'amber'}`}>{prediction.status.replaceAll('_', ' ')}</span></div>
    <div className="radar-meta"><span>Evidence: <b>{account.evidence_kind === 'demo_fixture' ? 'DEMO FIXTURE — SAMPLE DATA' : 'Source-backed'}</b></span><span>Score cutoff: <b>{formatDateTime(prediction.as_of)}</b></span><span>Generated: <b>{formatDateTime(prediction.generated_at)}</b></span></div>

    <section className="probability-grid" aria-label="Forecast horizons">{([7, 14, 30] as const).map(days => <article className="card probability" key={days}><span>{days}-day cumulative churn risk</span><strong>{formatRisk(prediction, days)}</strong><small>{prediction.status !== 'scored' ? 'Not scored — no numeric forecast' : `Prediction cutoff ${formatDateTime(prediction.as_of)}`}</small></article>)}</section>

    <div className="split stage-section">
      <section className="card"><h2>Prediction record</h2><div className="values"><p><span>Prediction ID</span><b>{prediction.prediction_id}</b></p><p><span>Prediction run ID</span><b>{prediction.prediction_run_id}</b></p><p><span>Score cutoff</span><b>{formatDateTime(prediction.as_of)}</b></p><p><span>Generated</span><b>{formatDateTime(prediction.generated_at)}</b></p><p><span>Model / feature version</span><b>{prediction.model_version ?? 'N/A'} / {prediction.feature_version ?? 'N/A'}</b></p><p><span>Calibration / label policy</span><b>{prediction.calibration_version ?? 'N/A'} / {prediction.label_policy_version ?? 'N/A'}</b></p></div></section>
      <section className="card"><h2>Reliability and data freshness</h2><p className="muted">Reliability describes evidence sufficiency and applicability, not probability of correctness.</p><div className="values"><p><span>Status</span><b><EvidencePills reliability={prediction.reliability.status} freshness={prediction.data_freshness.status} /></b></p><p><span>Reliability reasons</span><b>{reliabilityReasons.join('; ') || 'No reliability reason codes supplied'}</b></p><p><span>Input data available by</span><b>{formatDateTime(prediction.data_freshness.input_data_as_of)}</b></p><p><span>Stale sources</span><b>{prediction.data_freshness.stale_sources.join(', ') || 'None listed in fixture'}</b></p></div></section>
    </div>

    <div className="split">
      <section className="card"><div className="section-head"><div><h2>Personal baseline and recent behavior</h2><p className="muted">Observed account patterns, when present in the prediction output.</p></div><span className="pill neutral">Unavailable</span></div><p className="empty-trend">No baseline measurements or recent-to-baseline feature values are supplied. Sparse history cannot be assessed from this record.</p></section>
      <section className="card"><div className="section-head"><div><h2>Model signals</h2><p className="muted">Associations from the fitted model, not proven causes.</p></div><span className="pill neutral">{explanationHorizons.length ? 'Supplied' : 'Unavailable'}</span></div>
        {explanationHorizons.length ? <p className="empty-trend">Explanation payloads are present for {explanationHorizons.join(', ')}, but this frontend has no declared attribution shape to render their feature values safely.</p> : <p className="empty-trend">No horizon-specific model contributors are supplied with this prediction.</p>}
        <p className="caption">Decision route context: {account.route_reason || 'N/A'}. This synthetic route reason is not a prediction explanation.</p>
      </section>
    </div>

    <section className="card stage-section"><div className="section-head"><div><h2>Uncertainty</h2><p className="muted">Reliability is a separate evidence-quality gate.</p></div><span className="pill neutral">Not quantified</span></div><p className="empty-trend">Prediction uncertainty intervals are not quantified in the current output. No confidence interval or probability of correctness is inferred.</p></section>

    <div className="split">
      <section className="card"><h2>MRR and exposure</h2><p className="muted">Exposure is an MRR-weighted proxy, not confirmed lost revenue.</p><div className="values"><p><span>MRR</span><b>{formatMoney(account.mrr)}</b></p><p><span>At-risk exposure proxy (p30 × MRR)</span><b>{formatMoney(account.exposure_proxy)}</b></p></div><p className="caption">Currencies are not combined. A missing proxy is N/A, not zero.</p></section>
      <section className="card"><div className="section-head"><div><h2>Historical issued-score history</h2><p className="muted">Past prediction records only—not a future risk curve.</p></div><span className="pill neutral">Unavailable</span></div><p className="empty-trend">Only this synthetic cutoff is available for the account. No earlier issued-score snapshots or model-version history are connected.</p></section>
    </div>

    <section className="card stage-section"><div className="section-head"><div><h2>Related records</h2><p className="muted">Continue to Customer Insights or the linked Retention Actions case.</p></div></div><div className="record-links"><button type="button" className="btn outline" onClick={() => navigate(timelinePath(account.customer_id))}>Open Customer Insights</button>{relatedCase ? <button type="button" className="btn outline" onClick={() => navigate(casePath(relatedCase.id))}>Open Retention Actions · {relatedCase.id}</button> : <span className="pill neutral">No related case in this fixture</span>}</div></section>
  </div>;
}
