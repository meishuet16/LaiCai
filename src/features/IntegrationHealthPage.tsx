import { useEffect, useRef, useState } from 'react';
import { formatDateTime } from '../domain/format';
import type { RejectedEvent, SourceHealth } from '../domain/integration';
import { useIntegrationHealth } from '../hooks/useIntegrationHealth';

const statusTone = (status: SourceHealth['status']) => status === 'healthy' ? 'good' : status === 'warning' ? 'amber' : status === 'failed' ? 'red' : 'neutral';

function SourceDetails({ source, onClose }: { source: SourceHealth; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key === 'Tab') { event.preventDefault(); closeRef.current?.focus(); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      if (returnFocus?.isConnected) returnFocus.focus();
    };
  }, [onClose]);
  return <div className="detail-overlay integration-overlay" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="card detail-panel integration-detail-panel" role="dialog" aria-modal="true" aria-label={`${source.source} details`}>
      <div className="section-head"><div><p className="drawer-eyebrow">Synthetic source fixture</p><h2>{source.source} details</h2></div><button ref={closeRef} className="btn outline" onClick={onClose}>Close</button></div>
      <div className="detail-grid">
        <div className="values">
          <p><span>Connection status</span><b>{source.status}</b></p>
          <p><span>Freshness</span><b>{source.freshness}</b></p>
          <p><span>Source schema version</span><b>N/A — not supplied</b></p>
          <p><span>Mapping version</span><b>{source.mapping_version || 'N/A'}</b></p>
          <p><span>Event types</span><b>{source.event_types.length ? source.event_types.join(', ') : 'N/A'}</b></p>
        </div>
        <div className="values">
          <p><span>Last successful sync</span><b>{formatDateTime(source.last_success_at)}</b></p>
          <p><span>Last attempt</span><b>{formatDateTime(source.last_attempt_at)}</b></p>
          <p><span>Latest event occurrence</span><b>{formatDateTime(source.latest_occurred_at)}</b></p>
          <p><span>Latest availability / ingestion</span><b>{formatDateTime(source.latest_available_at)}</b></p>
          <p><span>Coverage dates</span><b>{source.available_from ?? 'N/A'} – {source.available_through ?? 'N/A'}</b></p>
        </div>
      </div>
      <div className="ops-strip"><span>Records processed <b>{source.processed_count.toLocaleString()}</b></span><span>Rejected <b>{source.rejected_count}</b></span><span>Errors <b>{source.error_count}</b></span></div>
      <p className="caption">Credentials, raw payloads, sensitivity labels and source provenance are not supplied to this demo view.</p>
    </section>
  </div>;
}

function RejectedEventDetails({ event, onClose }: { event: RejectedEvent; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKeyDown = (keyboardEvent: KeyboardEvent) => {
      if (keyboardEvent.key === 'Escape') { keyboardEvent.preventDefault(); onClose(); }
      if (keyboardEvent.key === 'Tab') { keyboardEvent.preventDefault(); closeRef.current?.focus(); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      if (returnFocus?.isConnected) returnFocus.focus();
    };
  }, [onClose]);
  return <div className="detail-overlay integration-overlay" onMouseDown={mouseEvent => { if (mouseEvent.target === mouseEvent.currentTarget) onClose(); }}>
    <section className="card detail-panel integration-detail-panel" role="dialog" aria-modal="true" aria-label="Rejected event safe metadata">
      <div className="section-head"><div><p className="drawer-eyebrow">Redacted inspector</p><h2>Rejected event</h2></div><button ref={closeRef} className="btn outline" onClick={onClose}>Close</button></div>
      <div className="values">
        <p><span>Recorded timestamp</span><b>{formatDateTime(event.at)}</b></p>
        <p><span>Source / event ID</span><b>{event.source} · {event.source_event_id}</b></p>
        <p><span>Sanitized rejection reason</span><b>{event.reason}</b></p>
        <p><span>Schema / mapping version</span><b>{event.schema_version || 'N/A'} / {event.mapping_version || 'N/A'}</b></p>
        <p><span>Redacted metadata only</span><b>{event.redacted_metadata || 'N/A'}</b></p>
      </div>
      <p className="caption">No raw payload, credentials, customer contact details or unredacted restricted fields are available here.</p>
    </section>
  </div>;
}

function suggestedCheck(title: string): string {
  const value = title.toLowerCase();
  if (value.includes('stale') || value.includes('sync')) return 'Check the source sync status and confirm new records are arriving.';
  if (value.includes('identity') || value.includes('mapping')) return 'Review the source-to-account mapping; keep unresolved identities quarantined and do not auto-merge.';
  if (value.includes('outcome') || value.includes('coverage') || value.includes('history')) return 'Review subscription-history coverage; incomplete observation must remain unknown.';
  return 'Review the source error and its schema/mapping version before changing configuration.';
}

export function IntegrationHealthPage() {
  const { status, data } = useIntegrationHealth();
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null);
  if (status === 'loading') return <p role="status">Loading integration health…</p>;
  if (status === 'error' || !data) return <div role="alert" className="notice ambernote">Integration health could not be loaded.</div>;

  const selected = data.sources.find(source => source.source === selectedSource);
  const rejectedEvent = data.rejected_events.find(event => event.id === selectedEvent);
  const coverage = data.coverage;
  const latestSuccessfulSync = data.sources.map(source => source.last_success_at).filter((value): value is string => value != null).sort().at(-1) ?? null;
  const availableSources = data.sources.filter(source => source.status === 'healthy' || source.status === 'warning').length;
  const degradedSources = data.sources.filter(source => source.status === 'warning' || source.status === 'failed' || source.status === 'unknown').length;
  const rejectedCount = data.sources.reduce((sum, source) => sum + source.rejected_count, 0);
  const errorCount = data.sources.reduce((sum, source) => sum + source.error_count, 0);
  const coverageRate = (value: number | null) => value == null ? 'N/A' : `${value}%`;
  const openSource = (sourceName: string | null) => {
    if (sourceName && data.sources.some(source => source.source === sourceName)) setSelectedSource(sourceName);
  };

  return <>
    <div className="integration-page-meta"><p className="muted page-intro">Source status, data coverage and quality signals from the current integration read model.</p><span className={`pill ${data.evidence_kind === 'synthetic' ? 'neutral' : 'good'}`}>{data.evidence_kind === 'synthetic' ? 'Synthetic fixture data' : 'Source-backed data'}</span></div>
    <section className="metrics integration-metrics" aria-label="Source summary">
      <article className="quick"><small>Configured sources</small><strong>{data.sources.length}</strong><span>Fixture records; connection is not verified</span></article>
      <article className="quick"><small>Sources reporting</small><strong>{availableSources}</strong><span>Healthy or warning status in this read model</span></article>
      <article className="quick alert"><small>Degraded / unknown</small><strong>{degradedSources}</strong><span>Warnings, failures and unknown status</span></article>
      <article className="quick"><small>Latest successful sync</small><strong className="sync-value">{formatDateTime(latestSuccessfulSync)}</strong><span>Latest timestamp present in fixtures</span></article>
    </section>

    <section className="source-cards" aria-label="Integration summaries">
      {data.sources.map(source => <article className="card source-card" key={source.source}>
        <div className="section-head"><h2>{source.source}</h2><span className={`pill ${statusTone(source.status)}`}>{source.status}</span></div>
        <div className="values"><p><span>Freshness</span><b>{source.freshness}</b></p><p><span>Last success</span><b>{formatDateTime(source.last_success_at)}</b></p><p><span>Mapping version</span><b>{source.mapping_version || 'N/A'}</b></p><p><span>Source schema version</span><b>N/A — not supplied</b></p></div>
        <button type="button" className="tablelink" onClick={() => setSelectedSource(source.source)}>Inspect source details →</button>
      </article>)}
    </section>

    <section className="card">
      <div className="section-head"><div><h2>Source health and freshness</h2><p className="muted">Occurrence time and availability/ingestion time are distinct fields.</p></div></div>
      <div className="tablewrap"><table><thead><tr><th>Source / type</th><th>Event types</th><th>Last successful sync</th><th>Latest event occurrence</th><th>Latest availability / ingestion</th><th>Freshness</th><th>Mapping</th><th>Rejected / errors</th><th>Status</th><th></th></tr></thead><tbody>
        {data.sources.map(source => <tr key={source.source}>
          <td><b>{source.source}</b><small>Source type N/A — not supplied</small></td>
          <td>{source.event_types.length ? source.event_types.join(', ') : 'N/A'}</td>
          <td>{formatDateTime(source.last_success_at)}</td>
          <td>{formatDateTime(source.latest_occurred_at)}</td>
          <td>{formatDateTime(source.latest_available_at)}</td>
          <td><span className={`pill ${source.freshness === 'fresh' ? 'good' : source.freshness === 'stale' ? 'amber' : 'neutral'}`}>{source.freshness}</span></td>
          <td>{source.mapping_version || 'N/A'}<small>Schema N/A</small></td>
          <td>{source.rejected_count} / {source.error_count}</td>
          <td><span className={`pill ${statusTone(source.status)}`}>{source.status}</span></td>
          <td><button type="button" className="tablelink" onClick={() => setSelectedSource(source.source)}>Inspect</button></td>
        </tr>)}
      </tbody></table></div>
    </section>

    <div className="split stage-section integration-summary-grid">
      <section className="card">
        <h2>Data coverage</h2>
        <div className="values">
          <p><span>Customer accounts mapped</span><b>{coverage.accounts_mapped}</b></p>
          <p><span>Unmatched identities</span><b>{coverage.accounts_unmatched}</b></p>
          <p><span>Separate quarantined-identity count</span><b>N/A — not supplied</b></p>
          <p><span>Active paying accounts</span><b>{coverage.active_paying}</b></p>
          <p><span>Missing MRR</span><b>{coverage.missing_mrr}</b></p>
          <p><span>Incomplete subscription history</span><b>{coverage.incomplete_subscription_history}</b></p>
          <p><span>Usage / billing / subscription coverage</span><b>{coverageRate(coverage.usage_percent)} / {coverageRate(coverage.billing_percent)} / {coverageRate(coverage.subscription_percent)}</b></p>
          <p><span>Absolute event totals</span><b>N/A — not supplied</b></p>
        </div>
        <p className="caption">The fixture alert says unmatched identities remain quarantined, but does not supply a separate quarantine count. Source coverage dates are available in source details.</p>
      </section>
      <section className="card">
        <div className="section-head"><div><h2>Data-quality alerts</h2><p className="muted">Suggested checks link to the related source where available.</p></div><span className="pill amber">{data.alerts.length} alerts</span></div>
        <div className="alert-list integration-alert-list">{data.alerts.length ? data.alerts.map(alert => {
          const matchingSource = alert.source ? data.sources.find(source => source.source === alert.source) : null;
          return <article className="alert-item integration-alert-item" key={alert.id}>
            <span className={`pill ${alert.severity === 'error' ? 'red' : 'amber'}`}>{alert.severity}</span>
            <div className="integration-alert-copy"><b>{alert.title}</b><p>{alert.detail}</p><small><b>Suggested next check:</b> {suggestedCheck(alert.title)}</small>
              {matchingSource ? <button type="button" className="tablelink" onClick={() => openSource(alert.source)}>Inspect {matchingSource.source} →</button> : <span className="integration-source-unavailable">Related source N/A — not supplied</span>}
            </div>
          </article>;
        }) : <p className="overview-empty">No alert records are available. This is not confirmation that all checks passed.</p>}</div>
      </section>
    </div>

    <section className="card stage-section">
      <div className="section-head"><div><h2>Rejected events and errors</h2><p className="muted">Sanitized reasons and counts only. Payloads are not shown.</p></div><div className="integration-reject-counts"><span>Rejected <b>{rejectedCount}</b></span><span>Errors <b>{errorCount}</b></span><span>Redacted examples <b>{data.rejected_events.length}</b></span></div></div>
      {data.rejected_events.length ? <div className="tablewrap"><table className="integration-rejected-table"><thead><tr><th>Recorded time</th><th>Source / event ID</th><th>Sanitized rejection reason</th><th>Schema / mapping</th><th>Inspector</th></tr></thead><tbody>
        {data.rejected_events.map(event => <tr key={event.id}>
          <td>{formatDateTime(event.at)}</td>
          <td>{event.source}<small>{event.source_event_id}</small></td>
          <td>{event.reason}</td>
          <td>{event.schema_version || 'N/A'} / {event.mapping_version || 'N/A'}</td>
          <td><button type="button" className="tablelink" onClick={() => setSelectedEvent(event.id)}>Inspect redacted metadata</button></td>
        </tr>)}
      </tbody></table></div> : <p className="empty-trend">No rejected-event examples are connected. Review source-level counters; an empty example list does not imply zero errors.</p>}
    </section>

    <section className="card stage-section integration-operations" aria-labelledby="integration-operations-title">
      <div className="section-head"><div><h2 id="integration-operations-title">Other data operations</h2><p className="muted">No production operation is available in this frontend.</p></div></div>
      <div className="integration-operation-list">
        <div><b>Historical import</b><span>Unavailable — no import service connected</span><button type="button" className="btn outline" disabled title="No import service is connected">Unavailable</button></div>
        <div><b>Sync / refresh</b><span>Unavailable — no synchronization service connected</span><button type="button" className="btn outline" disabled title="No synchronization service is connected">Unavailable</button></div>
        <div><b>Audit-safe report</b><span>Unavailable — no report service connected</span><button type="button" className="btn outline" disabled title="No report service is connected">Unavailable</button></div>
      </div>
      <p className="caption">The read-only source inspector is available for synthetic metadata. The demo-role selector is not authorization; production operations require server-side permissions.</p>
    </section>

    {selected ? <SourceDetails source={selected} onClose={() => setSelectedSource(null)} /> : null}
    {rejectedEvent ? <RejectedEventDetails event={rejectedEvent} onClose={() => setSelectedEvent(null)} /> : null}
  </>;
}
