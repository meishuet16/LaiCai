import { useApp } from '../app/AppContext';
import { casePath, timelinePath } from '../app/routes';
import { formatDateTime, formatMoney, formatRisk } from '../domain/format';
import { useDecisionCases } from '../hooks/useDecisionCases';
import { usePrediction } from '../hooks/usePrediction';
import { EvidencePills } from '../components/StatusPills';

export function PredictionDetailPage({ predictionId }: { predictionId: string }) {
  const { navigate } = useApp();
  const { status, account } = usePrediction(predictionId);
  const { cases } = useDecisionCases();
  if (status === 'loading') return <p role="status">Loading prediction…</p>;
  if (status === 'error') return <div role="alert" className="notice ambernote">Prediction could not be loaded.</div>;
  if (!account?.prediction) return <div className="card"><h2>Prediction not found</h2><p className="muted">It may have been removed or may not be available in this demo dataset.</p></div>;

  const prediction = account.prediction;
  const relatedCase = cases.find(item => item.customer_id === account.customer_id);
  const explanationHorizons = Object.keys(prediction.explanations_by_horizon);
  const reliabilityReasons = prediction.reliability.reasons.filter(Boolean);

  return <div className="prediction-detail-content">
    <div className="detail-title"><div><h2>{account.name}</h2><p className="muted">{account.customer_id} · {account.segment} · {account.plan}</p></div><span className={`pill ${prediction.status === 'scored' ? 'good' : 'amber'}`}>{prediction.status.replaceAll('_', ' ')}</span></div>
    <div className="radar-meta prediction-record-meta"><span>Evidence: <b>{account.evidence_kind === 'synthetic' ? 'Synthetic' : 'Source-backed'}</b></span><span>Cutoff: <b>{formatDateTime(prediction.as_of)}</b></span><span>Model: <b>{prediction.model_version || 'N/A'}</b></span></div>

    <section className="probability-grid" aria-label="Forecast horizons">{([7, 14, 30] as const).map(days => <article className="card probability" key={days}><span>{days}-day risk</span><strong>{formatRisk(prediction, days)}</strong>{prediction.status !== 'scored' && <small>No forecast available</small>}</article>)}</section>

    <div className="split stage-section">
      <section className="card"><h2>Evidence quality</h2><div className="values"><p><span>Reliability / freshness</span><b><EvidencePills reliability={prediction.reliability.status} freshness={prediction.data_freshness.status} /></b></p>{reliabilityReasons.length > 0 && <p><span>Notes</span><b>{reliabilityReasons.join(' · ')}</b></p>}{prediction.data_freshness.input_data_as_of && <p><span>Inputs through</span><b>{formatDateTime(prediction.data_freshness.input_data_as_of)}</b></p>}{prediction.data_freshness.stale_sources.length > 0 && <p><span>Stale sources</span><b>{prediction.data_freshness.stale_sources.join(', ')}</b></p>}</div><p className="caption">Evidence quality is separate from forecast confidence.</p></section>
      <section className="card"><h2>Exposure</h2><div className="values"><p><span>MRR</span><b>{formatMoney(account.mrr)}</b></p><p><span>At risk (p30 × MRR)</span><b>{formatMoney(account.exposure_proxy)}</b></p></div><p className="caption">Estimate only; currencies stay separate.</p></section>
    </div>

    <section className="card stage-section prediction-context"><div className="section-head"><h2>Model context</h2><span className="pill neutral">{explanationHorizons.length ? 'Details unavailable' : 'No signals supplied'}</span></div><p>{explanationHorizons.length ? `Attribution data exists for ${explanationHorizons.join(', ')}, but feature values are unavailable here.` : 'No model feature attribution is supplied.'}{account.route_reason ? ` Route: ${account.route_reason} (decision context only).` : ''}</p><p className="caption">Baseline and prior scores unavailable · uncertainty not quantified.</p></section>

    <section className="card stage-section"><div className="section-head"><h2>Related records</h2></div><div className="record-links"><button type="button" className="btn outline" onClick={() => navigate(timelinePath(account.customer_id))}>Customer Insights</button>{relatedCase ? <button type="button" className="btn outline" onClick={() => navigate(casePath(relatedCase.id))}>Retention case · {relatedCase.id}</button> : <span className="pill neutral">No related case</span>}</div></section>
  </div>;
}
