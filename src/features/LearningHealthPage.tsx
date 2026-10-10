import { formatDateTime } from '../domain/format.ts';
import { useLearning } from '../hooks/useLearning.ts';

const pct = (value: number | null) => value == null ? 'N/A' : `${Math.round(value * 100)}%`;
const label = (value: string) => value.replaceAll('_', ' ').toLowerCase();

export function LearningHealthPage() {
  const { status, data, error } = useLearning();
  if (status === 'loading') return <p role="status">Loading learning and model health…</p>;
  if (status === 'error' || !data) return <div role="alert" className="notice ambernote">{error ?? 'Learning status is unavailable.'}</div>;
  const horizons = [7, 14, 30].map(horizon => ({
    horizon,
    states: data.feedback.filter(item => item.horizon_days === horizon),
  }));
  const current = data.releases.find(release => release.release_role === 'current') ?? data.releases[0];
  const candidate = data.releases.find(release => release.release_role === 'candidate');
  return <div className="learning-page">
    <div className="learning-hero">
      <div><p className="eyebrow">Closed-loop governance</p><h2>Know what the model knows — and what it does not.</h2><p>Prediction coverage, outcome maturity and release gates are monitored without converting missing evidence into false performance claims.</p></div>
      <div className="learning-hero-status"><span className="status-dot"/><div><small>Current release</small><b>{current?.model_version ?? 'N/A'}</b><span>{current ? label(current.governance_state) : 'Not available'}</span></div></div>
    </div>

    <section className="metrics learning-metrics" aria-label="Model health summary">
      <article className="quick"><small>Prediction coverage</small><strong>{pct(data.summary.coverage_rate)}</strong><span>{data.summary.scored_accounts} of {data.summary.prospective_accounts} prospective accounts scored</span></article>
      <article className="quick"><small>Abstention rate</small><strong>{pct(data.summary.abstention_rate)}</strong><span>{data.summary.abstained_accounts} accounts routed without a numeric score</span></article>
      <article className="quick"><small>Horizon coherence</small><strong>{pct(data.summary.monotonicity_rate)}</strong><span>Scored forecasts satisfy p7 ≤ p14 ≤ p30</span></article>
      <article className="quick"><small>Fresh inputs</small><strong>{data.summary.fresh_accounts}</strong><span>Predictions with fully fresh source inputs</span></article>
    </section>

    <div className="split learning-grid">
      <section className="card">
        <div className="section-head"><div><h2>Outcome maturity by horizon</h2><p className="muted">Every forecast remains pending, incomplete or ineligible until its observation window and reconciliation checks are complete.</p></div><span className="pill neutral">As of {formatDateTime(data.as_of)}</span></div>
        <div className="maturity-list">{horizons.map(row => {
          const total = row.states.reduce((sum, state) => sum + state.count, 0);
          return <article key={row.horizon}><div className="maturity-head"><b>{row.horizon}-day outcome</b><span>{total} predictions</span></div><div className="maturity-bar">{row.states.map(state => <i key={state.feedback_state} className={`maturity-${state.feedback_state.toLowerCase()}`} style={{ width: `${total ? state.count / total * 100 : 0}%` }} title={`${state.feedback_state}: ${state.count}`}/>)}</div><div className="maturity-legend">{row.states.map(state => <span key={state.feedback_state}><i className={`maturity-${state.feedback_state.toLowerCase()}`}/>{label(state.feedback_state)} <b>{state.count}</b></span>)}</div></article>;
        })}</div>
      </section>
      <section className="card">
        <div className="section-head"><div><h2>Performance evidence</h2><p className="muted">Metrics unlock only after labels mature and pass reconciliation.</p></div><span className="pill amber">{label(data.performance.status)}</span></div>
        <div className="performance-lock"><span aria-hidden="true">⌁</span><h3>Waiting for mature outcomes</h3><p>PR-AUC, Brier score and Recall@K remain unavailable. This prevents partial windows from being reported as model quality.</p></div>
        <div className="values compact-values"><p><span>PR-AUC</span><b>{data.performance.pr_auc ?? 'N/A'}</b></p><p><span>Brier score</span><b>{data.performance.brier_score ?? 'N/A'}</b></p><p><span>Recall@K</span><b>{data.performance.recall_at_k ?? 'N/A'}</b></p></div>
      </section>
    </div>

    <section className="card release-card">
      <div className="section-head"><div><h2>Release governance</h2><p className="muted">Versioned artifacts and evidence gates keep model changes reversible and auditable.</p></div><span className="pill good">{data.releases.length} tracked releases</span></div>
      <div className="release-grid">{data.releases.map(release => <article key={release.model_version} className={`release-item ${release.release_role}`}><div className="release-title"><div><small>{release.release_role}</small><h3>{release.model_version}</h3></div><span className={`pill ${release.release_role === 'current' ? 'good' : 'amber'}`}>{label(release.governance_state)}</span></div><div className="values compact-values"><p><span>Features</span><b>{release.feature_version}</b></p><p><span>Calibration</span><b>{release.calibration_version}</b></p><p><span>Label policy</span><b>{release.label_policy_version}</b></p><p><span>Created</span><b>{formatDateTime(release.created_at)}</b></p></div><p className="release-reason">{release.decision_reason}</p></article>)}</div>
    </section>

    <section className="provenance-strip"><div><b>Evidence boundary</b><span>{data.dataset_provenance}. Operational workflow is connected to SQLite; real-world uplift and production model performance are not claimed.</span></div><div><b>Next gate</b><span>Reconcile mature 30-day outcomes, calculate metrics, review by segment, then approve or hold the candidate.</span></div></section>
  </div>;
}
