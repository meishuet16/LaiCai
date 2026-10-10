import { useApp } from '../app/AppContext';
import { timelinePath } from '../app/routes';
import { formatMoney, formatRisk } from '../domain/format';
import { useCustomers } from '../hooks/useCustomers';

export function CustomerTable() {
  const { query, setQuery, horizon, navigate } = useApp();
  const { status, rows, error } = useCustomers();
  return <section className="card queue">
    <div className="filters"><input aria-label="Filter accounts" value={query} onChange={event => setQuery(event.target.value)} placeholder="Filter by customer or ID"/><button className="btn outline" onClick={() => setQuery('')}>Clear</button></div>
    {status === 'loading' ? <p role="status">Loading accounts…</p> : status === 'error' ? <div role="alert" className="notice ambernote">{error}</div> : rows.length === 0 ? <p>No accounts match these filters.</p> : <div className="tablewrap"><table><thead><tr><th>Account</th><th>Route</th><th>Risk</th><th>Exposure proxy</th><th>Evidence</th><th>Case</th><th>Owner</th><th>Open</th></tr></thead><tbody>{rows.map(account => {
      const prediction = account.prediction;
      return <tr key={account.customer_id}><td><b>{account.name}</b><small>{account.customer_id} · {account.segment}</small></td><td><span className={`pill ${account.route === 'HUMAN_REVIEW' ? 'amber' : 'red'}`}>{account.route.replaceAll('_', ' ')}</span></td><td><b>{formatRisk(prediction, horizon)}</b><small>{horizon}d · {prediction?.as_of ?? 'N/A'}<br/>{prediction?.model_version ?? 'N/A'}</small></td><td><b>{formatMoney(account.exposure_proxy)}</b><small>p30 × as-of MRR</small></td><td>{prediction?.reliability.status.replaceAll('_', ' ') ?? 'N/A'}<small>{prediction?.data_freshness.status.replaceAll('_', ' ') ?? 'N/A'}</small></td><td>{account.case_status ?? 'N/A'}</td><td>{account.owner ?? 'Unassigned'}</td><td><a className="tablelink" href={timelinePath(account.customer_id)} onClick={event => { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); navigate(timelinePath(account.customer_id)); } }} aria-label={`Open ${account.name} timeline`}>Timeline →</a></td></tr>;
    })}</tbody></table></div>}
    <p className="caption">Synthetic demo records. Exposure is a ranking proxy, not expected loss.</p>
  </section>;
}
