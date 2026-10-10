import { useEffect, useState } from 'react';
import { useApp } from '../app/AppContext';
import { casePath, predictionPath, timelinePath } from '../app/routes';
import { customerLabel, type AccountRecord, type Freshness, type Reliability, type Route } from '../domain/customer';
import { formatDateTime, formatMoney } from '../domain/format';
import { isNonForecastAccount, predictionWarnings, probabilityAt } from '../domain/predictionPresentation';
import { useCustomers } from '../hooks/useCustomers';
import { RiskPill } from '../components/StatusPills';

type RiskBandFilter = 'all' | 'low' | 'medium' | 'high' | 'no_score';
type SortBy = 'risk' | 'exposure' | 'account';
const forecastRouteOptions: Route[] = ['PRIORITY_REVIEW', 'HUMAN_REVIEW', 'OBSERVE'];
const reliabilityOptions: Reliability[] = ['sufficient_evidence', 'limited_evidence', 'insufficient_evidence'];
const freshnessOptions: Freshness[] = ['fresh', 'partially_stale', 'stale', 'unknown'];
const label = (value: string) => value.replaceAll('_', ' ').toLowerCase();
const percent = (value: number | null) => value == null ? 'N/A' : `${Math.round(value * 100)}%`;
const bandAt = (account: AccountRecord, days: 7 | 14 | 30) => account.prediction?.risk_bands_by_horizon?.[days] ?? null;

function ReliabilityMark({ value }: { value: Reliability | null | undefined }) {
  const content = value === 'sufficient_evidence'
    ? { icon: '✓', text: 'Sufficient', description: 'Sufficient evidence' }
    : value === 'limited_evidence'
      ? { icon: '!', text: 'Limited', description: 'Limited evidence' }
      : value === 'insufficient_evidence'
        ? { icon: '×', text: 'Insufficient', description: 'Insufficient evidence' }
        : { icon: '?', text: 'Unknown', description: 'Reliability not supplied' };
  return <span className={`reliability-mark reliability-${value ?? 'unknown'}`} title={content.description} aria-label={`Reliability: ${content.description}`}><span aria-hidden="true">{content.icon}</span>{content.text}</span>;
}

function ForecastRow({ account, navigate }: { account: AccountRecord; navigate: (path: string) => void }) {
  const prediction = account.prediction;
  const p30Band = prediction?.risk_bands_by_horizon?.[30] ?? null;
  const warnings = predictionWarnings(prediction);
  return <tr>
    <td><button type="button" className="prediction-customer-link" disabled={!prediction} aria-label={`Open prediction details for ${customerLabel(account)}`} onClick={() => prediction && navigate(predictionPath(prediction.prediction_id))}>{customerLabel(account)}</button><small>{account.customer_id} · {account.segment ?? 'Segment unavailable'}</small><button type="button" className="tablelink prediction-customer-insight" onClick={() => navigate(timelinePath(account.customer_id))}>Customer Insights →</button></td>
    <td>{percent(probabilityAt(prediction, 7))}</td>
    <td>{percent(probabilityAt(prediction, 14))}</td>
    <td><b>{percent(probabilityAt(prediction, 30))}</b><RiskPill band={p30Band} />{warnings.length ? <span className="pill amber prediction-warning" title="Supplied horizon probabilities need review">Check horizons</span> : null}</td>
    <td><ReliabilityMark value={prediction?.reliability.status} />{prediction?.status === 'abstained' ? <small>{prediction.reliability.reasons.join('; ') || account.route_reason || 'No abstention reason supplied'}</small> : null}</td>
    <td><div className="prediction-money-stack"><small>Exposure proxy</small><b>{formatMoney(account.exposure_proxy)}</b><small>MRR</small><span>{formatMoney(account.mrr)}</span></div></td>
    <td><span className="pill neutral prediction-route-pill">{label(account.route)}</span><small>{account.case_status ? label(account.case_status) : 'No linked case'}</small>{account.case_id ? <button type="button" className="tablelink" onClick={() => navigate(casePath(account.case_id!))}>Open case →</button> : null}</td>
  </tr>;
}

function NonForecastTable({ title, note, accounts, navigate }: { title: string; note: string; accounts: AccountRecord[]; navigate: (path: string) => void }) {
  return <section className="card stage-section">
    <div className="section-head"><div><h2>{title}</h2><p className="muted">{note}</p></div><span className="pill neutral">{accounts.length} accounts</span></div>
    {accounts.length ? <div className="tablewrap"><table className="prediction-nonforecast-table"><thead><tr><th>Customer / account ID</th><th>Forecast status</th><th>Reason</th><th>MRR</th><th>Customer Insights</th></tr></thead><tbody>{accounts.map(account => <tr key={account.customer_id}>
      <td><b>{customerLabel(account)}</b><small>{account.customer_id} · {account.segment ?? 'Segment unavailable'}</small></td>
      <td><span className={`pill ${account.route === 'KNOWN_CANCELLATION' ? 'amber' : 'neutral'}`}>{account.route === 'KNOWN_CANCELLATION' ? 'Known Cancellation — Not a Forecast' : 'Not eligible — Not a Forecast'}</span></td>
      <td>{account.route_reason || 'No reason supplied'}</td>
      <td>{formatMoney(account.mrr)}</td>
      <td><button type="button" className="tablelink" onClick={() => navigate(timelinePath(account.customer_id))}>Open customer →</button></td>
    </tr>)}</tbody></table></div> : <p className="overview-empty">No accounts in this state are available for the current search and currency selection.</p>}
  </section>;
}

export function PredictionRadarPage() {
  const { navigate, horizon, query, setQuery } = useApp();
  const { status, rows, error } = useCustomers();
  const [band, setBand] = useState<RiskBandFilter>('all');
  const [route, setRoute] = useState<Route | 'all'>('all');
  const [reliability, setReliability] = useState<Reliability | 'all'>('all');
  const [freshness, setFreshness] = useState<Freshness | 'all'>('all');
  const [segment, setSegment] = useState('all');
  const [owner, setOwner] = useState('all');
  const [sortBy, setSortBy] = useState<SortBy>('risk');
  const [page, setPage] = useState(0);

  useEffect(() => { setPage(0); }, [band, route, reliability, freshness, segment, owner, query, horizon]);
  if (status === 'loading') return <p role="status">Loading prediction records…</p>;
  if (status === 'unavailable') return <section className="card unavailable-state"><h2>Churn Prediction is not connected</h2><p>{error}</p><p>The active backend has no browser-safe prediction read, evaluation, or historical prediction API. Connected mode does not substitute local demo scores.</p></section>;
  if (status === 'error') return <div role="alert" className="notice ambernote">{error}</div>;

  const nonForecast = rows.filter(isNonForecastAccount);
  const knownCancellations = nonForecast.filter(account => account.route === 'KNOWN_CANCELLATION' || account.prediction?.status === 'known_cancellation');
  const notEligible = nonForecast.filter(account => account.route === 'NOT_ELIGIBLE' || account.prediction?.status === 'not_eligible');
  const forecastRows = rows.filter(account => !isNonForecastAccount(account));
  const eligible = forecastRows;
  const scored = eligible.filter(account => account.prediction?.status === 'scored');
  const abstainedOrInsufficient = eligible.filter(account => account.prediction?.status === 'abstained' || account.prediction?.reliability.status === 'insufficient_evidence');
  const bands = (['low', 'medium', 'high'] as const).map(key => ({ key, count: scored.filter(account => bandAt(account, horizon) === key).length }));
  const maxBand = Math.max(1, ...bands.map(item => item.count));
  const coveragePercent = eligible.length ? Math.round(scored.length / eligible.length * 100) : null;
  const predictions = rows.flatMap(account => account.prediction ? [account.prediction] : []);
  const latestAsOf = predictions.map(prediction => prediction.as_of).filter((value): value is string => value !== null).sort().at(-1) ?? null;
  const cutoffCount = new Set(predictions.map(prediction => prediction.as_of).filter((value): value is string => value !== null)).size;
  const versions = [...new Set(predictions.map(prediction => prediction.model_version).filter((value): value is string => Boolean(value)))];
  const modelLabel = versions.length === 1 ? versions[0] : versions.length > 1 ? 'Multiple versions' : 'N/A';
  const exposureCurrencies = [...new Set(scored.flatMap(account => account.mrr ? [account.mrr.currency] : account.exposure_proxy ? [account.exposure_proxy.currency] : []))].sort();
  const exposureByCurrency = exposureCurrencies.map(currency => {
    const available = scored.filter(account => account.exposure_proxy?.currency === currency);
    const scoredWithCurrencyMrr = scored.filter(account => account.mrr?.currency === currency);
    const amount = available.reduce((sum, account) => sum + (account.exposure_proxy?.amount_minor ?? 0), 0);
    return { money: available.length ? { amount_minor: amount, currency } : null, available: available.length, currency, eligible: scoredWithCurrencyMrr.length };
  });
  const warningCount = scored.filter(account => predictionWarnings(account.prediction).length > 0).length;
  const segments = [...new Set(forecastRows.map(account => account.segment).filter((value): value is string => Boolean(value)))].sort();
  const owners = [...new Set(forecastRows.flatMap(account => account.owner ? [account.owner] : []))].sort();

  const filtered = forecastRows.filter(account =>
    account.customer_id.toLowerCase().includes(query.toLowerCase()) &&
    (band === 'all' || (band === 'no_score' ? probabilityAt(account.prediction, horizon) == null : bandAt(account, horizon) === band)) &&
    (route === 'all' || account.route === route) &&
    (reliability === 'all' || account.prediction?.reliability.status === reliability) &&
    (freshness === 'all' || account.prediction?.data_freshness.status === freshness) &&
    (segment === 'all' || account.segment === segment) &&
    (owner === 'all' || (owner === 'unassigned' ? !account.owner : account.owner === owner))
  );
  const sorted = [...filtered].sort((left, right) => {
    if (sortBy === 'account') return left.customer_id.localeCompare(right.customer_id);
    if (sortBy === 'exposure') {
      const leftMoney = left.exposure_proxy;
      const rightMoney = right.exposure_proxy;
      if (!leftMoney && !rightMoney) return left.customer_id.localeCompare(right.customer_id);
      if (!leftMoney) return 1;
      if (!rightMoney) return -1;
      if (leftMoney.currency !== rightMoney.currency) return leftMoney.currency.localeCompare(rightMoney.currency);
      return rightMoney.amount_minor - leftMoney.amount_minor;
    }
    const leftRisk = probabilityAt(left.prediction, horizon);
    const rightRisk = probabilityAt(right.prediction, horizon);
    if (leftRisk == null && rightRisk == null) return left.customer_id.localeCompare(right.customer_id);
    if (leftRisk == null) return 1;
    if (rightRisk == null) return -1;
    return rightRisk - leftRisk;
  });
  const pageSize = 10;
  const pageCount = Math.ceil(sorted.length / pageSize);
  const safePage = Math.min(page, Math.max(0, pageCount - 1));
  const visible = sorted.slice(safePage * pageSize, (safePage + 1) * pageSize);
  const clearFilters = () => { setQuery(''); setBand('all'); setRoute('all'); setReliability('all'); setFreshness('all'); setSegment('all'); setOwner('all'); setSortBy('risk'); setPage(0); };

  return <>
    <p className="muted page-intro">Reliability describes evidence sufficiency, not a probability that a score is correct. In Demo Fixture mode, probability values are illustrative and are not trained-model outputs.</p>
    <div className="radar-meta"><span>Selected horizon: <b>{horizon} days</b></span><span>As of <b>{formatDateTime(latestAsOf)}</b></span><span>Model: <b>{modelLabel}</b></span><span className="pill neutral">Synthetic demo data</span></div>

    <section className="metrics prediction-metrics" aria-label="Prediction coverage">
      <article className="quick"><small>Eligible accounts</small><strong>{eligible.length}</strong><span>Excludes known cancellations and ineligible accounts</span></article>
      <article className="quick"><small>Valid predictions</small><strong>{scored.length}</strong><span>Scored accounts with supplied horizon outputs</span></article>
      <article className="quick"><small>Abstained / insufficient evidence</small><strong>{abstainedOrInsufficient.length}</strong><span>Shown without numeric churn probabilities</span></article>
      <article className="quick"><small>Prediction coverage</small><strong>{coveragePercent == null ? 'N/A' : `${coveragePercent}%`}</strong><span>{scored.length} scored of {eligible.length} eligible accounts</span></article>
    </section>

    <div className="split prediction-summary-grid">
      <section className="card"><div className="section-head"><div><h2>{horizon}-day model-policy risk bands</h2><p className="muted">Only backend-supplied policy bands are counted. Select a band to filter the table.</p></div>{warningCount ? <span className="pill amber">{warningCount} score-output warning{warningCount === 1 ? '' : 's'}</span> : null}</div>
        <div className="distribution" role="group" aria-label={`${horizon}-day risk bands`}>
          {bands.every(item => item.count === 0) ? <p className="empty-trend">Policy risk bands are unavailable for this prediction set. Numeric probabilities are not assigned client-side categories.</p> : bands.map(item => <button type="button" aria-pressed={band === item.key} className={`risk-band risk-${item.key}${band === item.key ? ' selected' : ''}`} key={item.key} onClick={() => setBand(band === item.key ? 'all' : item.key)}>
            <span>{item.key}</span><i aria-hidden="true"><em style={{ width: `${(item.count / maxBand) * 100}%` }} /></i><b>{item.count}</b><small>{scored.length ? `${Math.round(item.count / scored.length * 100)}%` : 'N/A'}</small>
          </button>)}
        </div>
        <p className="caption">No frontend risk thresholds are applied. If the selected model supplies no bands, the distribution is unavailable. Cumulative outputs should satisfy p7 ≤ p14 ≤ p30.</p>
      </section>
      <section className="card"><h2>MRR-weighted exposure proxy</h2><p className="muted">Available p30 × as-of MRR estimates only—not confirmed lost revenue. Currency totals remain separate.</p>
        {exposureByCurrency.length ? <div className="values">{exposureByCurrency.map(item => <p key={item.currency}><span>{item.currency} · {item.available}/{item.eligible} scored accounts with MRR</span><b>{formatMoney(item.money)}</b></p>)}</div> : <p className="empty-trend">N/A — no MRR-weighted exposure proxy is supplied for these accounts.</p>}
        <p className="caption">Missing or unavailable exposure is not treated as zero; displayed totals cover only records with a supplied proxy.</p>
      </section>
    </div>

    <div className="split prediction-summary-grid">
      <section className="card"><div className="section-head"><div><h2>Historical issued-score history</h2><p className="muted">Past predictions only; this is not a future risk curve.</p></div><span className="pill neutral">{cutoffCount ? `${cutoffCount} cutoff${cutoffCount === 1 ? '' : 's'} in current read` : 'Unavailable'}</span></div>
        <p className="empty-trend">The current account read provides no per-account historical score stream. Earlier issued predictions and intervening scores are unavailable; none are inferred.</p>
      </section>
      <section className="card"><div className="section-head"><div><h2>Model evaluation</h2><p className="muted">Held-out evidence only</p></div><span className="pill neutral">Not connected</span></div>
        <p className="empty-trend">Evaluation results not connected — no held-out metrics, mature label counts, or evaluation sample size are supplied.</p>
      </section>
    </div>

    <section className="card stage-section"><div className="section-head"><div><h2>Account predictions</h2><p className="muted">All stored 7-, 14- and 30-day outputs are shown; selecting a row opens its forecast details.</p></div><span className="pill neutral">{filtered.length} matching · {sorted.length} sorted</span></div>
      <div className="filters radar-filters">
        <input aria-label="Search account ID" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search account ID" />
        <select aria-label="Selected-horizon model risk band" value={band} onChange={event => setBand(event.target.value as RiskBandFilter)}><option value="all">All policy bands</option><option value="low">Low (model policy)</option><option value="medium">Medium (model policy)</option><option value="high">High (model policy)</option><option value="no_score">No score / abstained</option></select>
        <select aria-label="Decision route" value={route} onChange={event => setRoute(event.target.value as Route | 'all')}><option value="all">All forecast routes</option>{forecastRouteOptions.map(value => <option key={value} value={value}>{label(value)}</option>)}</select>
        <select aria-label="Reliability status" value={reliability} onChange={event => setReliability(event.target.value as Reliability | 'all')}><option value="all">All reliability</option>{reliabilityOptions.map(value => <option key={value} value={value}>{label(value)}</option>)}</select>
        <select aria-label="Data freshness" value={freshness} onChange={event => setFreshness(event.target.value as Freshness | 'all')}><option value="all">All freshness</option>{freshnessOptions.map(value => <option key={value} value={value}>{label(value)}</option>)}</select>
        <select aria-label="Segment" value={segment} onChange={event => setSegment(event.target.value)}><option value="all">All segments</option>{segments.map(value => <option key={value} value={value}>{value}</option>)}</select>
        <select aria-label="Owner" value={owner} onChange={event => setOwner(event.target.value)}><option value="all">All owners</option>{owners.map(value => <option key={value} value={value}>{value}</option>)}{forecastRows.some(account => !account.owner) ? <option value="unassigned">Unassigned</option> : null}</select>
        <label className="sort-control">Sort by<select aria-label="Sort accounts" value={sortBy} onChange={event => { setSortBy(event.target.value as SortBy); setPage(0); }}><option value="risk">Highest selected-horizon risk</option><option value="exposure">Highest exposure proxy</option><option value="account">Account ID</option></select></label>
        <button type="button" className="btn outline" onClick={clearFilters}>Clear filters</button>
      </div>
      {visible.length ? <div className="tablewrap"><table className="prediction-account-table"><thead><tr><th>Customer</th><th>p7</th><th>p14</th><th>p30 + 30-day band</th><th>Reliability</th><th>Exposure / MRR</th><th>Case / route</th></tr></thead><tbody>{visible.map(account => <ForecastRow key={account.customer_id} account={account} navigate={navigate} />)}</tbody></table></div> : <p className="empty-trend">No forecast accounts match these filters. Try clearing one or more filters. Missing probabilities remain N/A.</p>}
      <div className="pagination"><span>Page {pageCount ? safePage + 1 : 0} of {pageCount} · {filtered.length} accounts</span><div><button type="button" className="btn outline" disabled={safePage === 0} onClick={() => setPage(value => Math.max(0, value - 1))}>Previous</button><button type="button" className="btn outline" disabled={safePage >= pageCount - 1} onClick={() => setPage(value => Math.min(pageCount - 1, value + 1))}>Next</button></div></div>
      <p className="caption">Probabilities come directly from each stored prediction output. The risk filter follows the selected horizon; the band beside p30 is the 30-day band. Ordering issues are flagged without changing supplied values.</p>
    </section>

    <NonForecastTable title="Known Cancellation — Not a Forecast" note="Accounts whose cancellation was already known at the prediction cutoff are not prospective churn forecasts." accounts={knownCancellations} navigate={navigate} />
    <NonForecastTable title="Not eligible — Not a Forecast" note="These records do not have an eligible forecast in the current read model." accounts={notEligible} navigate={navigate} />
  </>;
}
