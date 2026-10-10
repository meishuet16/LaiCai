import { useMemo } from 'react';
import { useApp } from '../app/AppContext';
import { casePath, timelinePath } from '../app/routes';
import type { AccountRecord, Currency, Freshness, Horizon, Money } from '../domain/customer';
import { formatDateTime, formatMoney, formatRisk } from '../domain/format';
import { summarizeOverview, type OverviewActivity } from '../domain/overview';
import { useDashboard } from '../hooks/useDashboard';

const horizons: Horizon[] = [7, 14, 30];
const currencies: Currency[] = ['MYR', 'SGD'];
const riskBands = [
  { band: 'low', label: 'Low risk', color: 'var(--forest)', threshold: '<30%' },
  { band: 'medium', label: 'Medium risk', color: '#bd9859', threshold: '30–59%' },
  { band: 'high', label: 'High risk', color: 'var(--terracotta)', threshold: '≥60%' },
] as const;

const inputFreshnessLabels: Record<Freshness, string> = {
  fresh: 'fresh',
  partially_stale: 'partially stale',
  stale: 'stale',
  unknown: 'unknown',
};

function DataFreshnessLine({
  sources,
  inputs,
  onOpen,
}: {
  sources: Record<'fresh' | 'stale' | 'unknown', number>;
  inputs: Record<Freshness, number>;
  onOpen: () => void;
}) {
  const sourceCount = Object.values(sources).reduce((total, count) => total + count, 0);
  const inputCount = Object.values(inputs).reduce((total, count) => total + count, 0);
  const sourceLabel = sourceCount
    ? Object.entries(sources).filter(([, count]) => count > 0).map(([status, count]) => `${count} ${status}`).join(' · ')
    : 'N/A';
  const inputLabel = inputCount
    ? Object.entries(inputs).filter(([, count]) => count > 0).map(([status, count]) => `${count} ${inputFreshnessLabels[status as Freshness]}`).join(' · ')
    : 'N/A';

  return <button type="button" className="overview-freshness-line" onClick={onOpen}>
    <span className="overview-freshness-title">Data freshness</span>
    <span>Sources: {sourceLabel}</span>
    <span>Prediction inputs: {inputLabel}</span>
    <span className="overview-freshness-link">Open Data Integration →</span>
  </button>;
}

function RiskDistribution({
  counts,
  scored,
  totalAccounts,
  horizon,
  onHorizonChange,
  cutoff,
  modelVersion,
  knownCancellations,
  abstained,
  insufficientEvidence,
}: {
  counts: Record<'low' | 'medium' | 'high', number>;
  scored: number;
  totalAccounts: number;
  horizon: Horizon;
  onHorizonChange: (horizon: Horizon) => void;
  cutoff: string;
  modelVersion: string;
  knownCancellations: number;
  abstained: number;
  insufficientEvidence: number;
}) {
  const radius = 74;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const segments = riskBands.map(item => {
    const amount = scored === 0 ? 0 : counts[item.band] / scored * circumference;
    const segment = { ...item, amount, offset };
    offset += amount;
    return segment;
  });
  const notForecasted = Math.max(0, totalAccounts - scored);

  return <section className="card overview-risk-card" aria-labelledby="overview-risk-title">
    <div className="section-head overview-risk-heading">
      <div className="overview-risk-title-block">
        <h2 id="overview-risk-title">Churn risk distribution</h2>
        <div className="overview-risk-meta">
          <span className="pill neutral">Mock Demo · synthetic data</span>
          <span>As of {formatDateTime(cutoff)}</span>
          <span>Model {modelVersion}</span>
        </div>
      </div>
      <div className="seg overview-horizon-toggle" role="group" aria-label="Churn risk horizon">
        {horizons.map(days => <button type="button" key={days} aria-pressed={horizon === days} className={horizon === days ? 'on' : ''} onClick={() => onHorizonChange(days)}>{days}d</button>)}
      </div>
    </div>
    <div className="overview-risk-content">
      <div className="overview-ring" role="img" aria-label={`${horizon}-day churn risk distribution. ${counts.low} low, ${counts.medium} medium, ${counts.high} high risk accounts; ${notForecasted} accounts are not forecasted.`}>
        <svg viewBox="0 0 200 200" aria-hidden="true" focusable="false">
          <circle className="overview-ring-track" cx="100" cy="100" r={radius} />
          {segments.map(item => <circle key={item.band} cx="100" cy="100" r={radius} fill="none" stroke={item.color} strokeWidth="23" strokeDasharray={`${item.amount} ${circumference - item.amount}`} strokeDashoffset={-item.offset} transform="rotate(-90 100 100)" />)}
        </svg>
        <div className="overview-ring-center"><small>{horizon}-day scored</small><strong>{scored}</strong></div>
      </div>
      <div className="overview-risk-legend" aria-label="Risk band counts">
        {segments.map(item => <div className="overview-risk-item" key={item.band}>
          <span className="overview-risk-key" style={{ backgroundColor: item.color }} aria-hidden="true" />
          <span className="overview-risk-name">{item.label}<small>{item.threshold}</small></span>
          <b>{scored ? `${Math.round(counts[item.band] / scored * 100)}%` : 'N/A'}</b>
          <strong>{counts[item.band]}</strong>
        </div>)}
        <div className="overview-risk-item overview-unscored"><span className="overview-risk-key" aria-hidden="true"/><span className="overview-risk-name">Not forecasted<small>Known cancellation, abstained, or ineligible</small></span><b>{totalAccounts ? `${Math.round(notForecasted / totalAccounts * 100)}%` : 'N/A'}</b><strong>{notForecasted}</strong></div>
      </div>
    </div>
    <div className="overview-nonforecast" aria-label="Accounts outside the forecast">
      <div><span>Known cancellation — not a forecast</span><b>{knownCancellations}</b></div>
      <div><span>Abstained</span><b>{abstained}</b></div>
      <div><span>Insufficient evidence</span><b>{insufficientEvidence}</b></div>
      <p>Abstained and insufficient-evidence counts may overlap.</p>
    </div>
  </section>;
}

function RevenueExposure({
  exposureByCurrency,
  exposureAccountCount,
  myrReportedMrr,
  myrAccountCount,
  sgdAccountCount,
  missingMrr,
}: {
  exposureByCurrency: Partial<Record<Currency, { amount_minor: number; currency: Currency }>>;
  exposureAccountCount: number;
  myrReportedMrr: Money | null;
  myrAccountCount: number;
  sgdAccountCount: number;
  missingMrr: number;
}) {
  return <section className="card overview-revenue-card" aria-label="Monthly recurring revenue and exposure">
    <div className="section-head"><div><h2>Revenue exposure</h2><p className="muted">Estimated MRR-weighted exposure is not confirmed lost revenue.</p></div></div>
    <div className="overview-revenue-grid">
      <article className="overview-exposure-panel">
        <h3>MRR-weighted exposure proxy</h3>
        <p className="overview-panel-caption">Based on available p30 × MRR exposure values; currencies stay separate.</p>
        <div className="overview-currency-values">
          {currencies.map(currency => <div className="overview-currency-value" key={currency}>
            <small>{currency}</small>
            <strong>{exposureByCurrency[currency] ? formatMoney(exposureByCurrency[currency]!) : 'N/A'}</strong>
          </div>)}
        </div>
        <p className="caption">Available for {exposureAccountCount} accounts. Other values are excluded; this is an estimate, not recognized or lost revenue.</p>
      </article>
      <article className="overview-mrr-context">
        <div><h3>Reported monthly recurring revenue</h3><small>MYR context only · no currency conversion</small></div>
        <strong>{formatMoney(myrReportedMrr)}</strong>
        <div className="overview-mrr-coverage">
          <span>Accounts included in MYR total</span><b>{myrReportedMrr ? myrAccountCount : 'N/A'}</b>
          <span>SGD MRR accounts excluded</span><b>{sgdAccountCount}</b>
          <span>Accounts with missing MRR</span><b>{missingMrr}</b>
        </div>
      </article>
    </div>
  </section>;
}

function PriorityPreview({
  cases,
  accounts,
  horizon,
  onOpenCase,
  onOpenCustomer,
  onOpenQueue,
}: {
  cases: ReturnType<typeof summarizeOverview>['priorityCases'];
  accounts: AccountRecord[];
  horizon: Horizon;
  onOpenCase: (caseId: string) => void;
  onOpenCustomer: (customerId: string) => void;
  onOpenQueue: () => void;
}) {
  const accountById = new Map(accounts.map(account => [account.customer_id, account]));

  return <section className="card overview-secondary-card" aria-labelledby="overview-priority-title">
    <div className="section-head">
      <div><h2 id="overview-priority-title">Priority review cases</h2><p className="muted">Current service order; no client-side ranking is applied.</p></div>
      <button type="button" className="tablelink" onClick={onOpenQueue}>Open Retention Actions →</button>
    </div>
    {cases.length ? <ol className="overview-priority-list">
      {cases.map(item => {
        const account = accountById.get(item.customer_id);
        const probability = account?.prediction?.status === 'scored' ? (horizon === 7 ? account.prediction.p_churn_7d : horizon === 14 ? account.prediction.p_churn_14d : account.prediction.p_churn_30d) : null;
        return <li key={item.id}>
          <div className="overview-priority-main">
            <button type="button" className="overview-customer-link" onClick={() => onOpenCustomer(item.customer_id)}>{account?.name ?? item.customer_id}</button>
            <span className="overview-customer-id">{item.customer_id} · {item.status.replaceAll('_', ' ').toLowerCase()}</span>
            <span className="overview-priority-reason">{item.route_reason}</span>
            <span className="overview-priority-badges"><span className={`pill ${account?.prediction?.reliability.status === 'sufficient_evidence' ? 'good' : 'amber'}`}>{account?.prediction?.reliability.status?.replaceAll('_', ' ') ?? 'Reliability N/A'}</span><span className={`pill ${account?.prediction?.data_freshness.status === 'fresh' ? 'good' : account?.prediction?.data_freshness.status === 'unknown' ? 'neutral' : 'amber'}`}>{account?.prediction?.data_freshness.status?.replaceAll('_', ' ') ?? 'Freshness N/A'}</span></span>
          </div>
          <div className="overview-priority-value"><small>{horizon}d risk</small><b>{probability == null ? 'N/A' : `${Math.round(probability * 100)}%`}</b><small>MRR exposure</small><b>{formatMoney(account?.exposure_proxy ?? null)}</b><button type="button" className="table-action" onClick={() => onOpenCase(item.id)}>Open case</button></div>
        </li>;
      })}
    </ol> : <p className="overview-empty">No priority review cases are available.</p>}
  </section>;
}

function RecentActivity({ items, onOpen }: { items: OverviewActivity[]; onOpen: (item: OverviewActivity) => void }) {
  return <section className="card overview-secondary-card" aria-labelledby="overview-activity-title">
    <div className="section-head"><div><h2 id="overview-activity-title">Recent activity</h2><p className="muted">Prediction records, case audit entries and rejected source records.</p></div></div>
    {items.length ? <ol className="overview-activity-list">
      {items.map(item => <li key={item.id}>
        <button type="button" className="overview-activity-button" onClick={() => onOpen(item)}>
          <span className="overview-activity-main"><b>{item.title}</b><small>{item.detail}</small></span>
          <time dateTime={item.at}>{formatDateTime(item.at)}</time>
        </button>
      </li>)}
    </ol> : <p className="overview-empty">No recorded activity is available.</p>}
  </section>;
}

export function CommandCenterPage() {
  const { horizon, setHorizon, navigate } = useApp();
  const { snapshot, status, error } = useDashboard();
  const summary = useMemo(() => snapshot ? summarizeOverview(snapshot.accounts, snapshot.cases, snapshot.integration, snapshot.as_of, horizon) : null, [snapshot, horizon]);

  if (status === 'loading') return <p role="status">Loading Business Overview…</p>;
  if (status === 'error' || !snapshot || !summary) return <div className="notice ambernote" role="alert">{error ?? 'Business Overview is unavailable.'}</div>;

  const modelVersion = summary.modelVersions.length === 1 ? summary.modelVersions[0] : summary.modelVersions.length ? `Multiple (${summary.modelVersions.length})` : 'N/A';
  const openActivity = (item: OverviewActivity) => {
    if (item.target.type === 'prediction') navigate('/predictions');
    else if (item.target.type === 'integration') navigate('/integrations');
    else navigate(casePath(item.target.caseId));
  };

  return <>
    <section className="metrics overview-kpis" aria-label="Business Overview key metrics">
      <article className="quick"><small>Eligible accounts</small><strong>{summary.eligibleAccounts}</strong></article>
      <article className="quick"><small>Valid predictions</small><strong>{summary.validPredictions}</strong></article>
      <article className="quick"><small>Open retention cases</small><strong>{summary.openCases}</strong></article>
      <article className="quick overview-workload-kpi" aria-label={`${summary.pendingCases} pending cases and ${summary.overdueCases} overdue cases`}>
        <small>Case workload</small>
        <div className="overview-workload-values"><span><b>{summary.pendingCases}</b><small>Pending</small></span><span><b>{summary.overdueCases}</b><small>Overdue</small></span></div>
      </article>
    </section>

    <DataFreshnessLine sources={summary.sourceFreshness} inputs={summary.inputFreshness} onOpen={() => navigate('/integrations')} />

    <RiskDistribution
      counts={summary.riskCounts}
      scored={summary.validPredictions}
      totalAccounts={snapshot.accounts.length}
      horizon={horizon}
      onHorizonChange={setHorizon}
      cutoff={snapshot.as_of}
      modelVersion={modelVersion}
      knownCancellations={summary.knownCancellations}
      abstained={summary.abstained}
      insufficientEvidence={summary.insufficientEvidence}
    />

    <RevenueExposure
      exposureByCurrency={summary.exposureByCurrency}
      exposureAccountCount={summary.exposureAccountCount}
      myrReportedMrr={summary.myrReportedMrr}
      myrAccountCount={summary.myrAccountCount}
      sgdAccountCount={summary.sgdAccountCount}
      missingMrr={summary.missingMrr}
    />

    <div className="overview-secondary-grid">
      <PriorityPreview
        cases={summary.priorityCases}
        accounts={snapshot.accounts}
        horizon={horizon}
        onOpenCase={caseId => navigate(casePath(caseId))}
        onOpenCustomer={customerId => navigate(timelinePath(customerId))}
        onOpenQueue={() => navigate('/cases')}
      />
      <RecentActivity items={summary.recentActivity} onOpen={openActivity} />
    </div>
  </>;
}
