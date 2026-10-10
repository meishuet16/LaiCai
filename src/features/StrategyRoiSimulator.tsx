import { useState } from 'react';
import type { AccountRecord, Currency } from '../domain/customer';
import type { Capacity, DecisionCase } from '../domain/decision';
import { calculateScenario } from '../domain/scenario';
import { formatMoney, formatRisk, majorToMinor, minorToMajor } from '../domain/format';
import { proposalsFor } from '../services/decisionService';

type Strategy = 'exposure' | 'risk';
type Candidate = { item: DecisionCase; account: AccountRecord; action: ReturnType<typeof proposalsFor>[number] };

type SliderProps = {
  id: string;
  label: string;
  value: number;
  valueLabel: string;
  min: number;
  max: number;
  step: number;
  minLabel: string;
  maxLabel: string;
  onChange: (value: number) => void;
};

function ScenarioSlider({ id, label, value, valueLabel, min, max, step, minLabel, maxLabel, onChange }: SliderProps) {
  return <div className="simulator-slider">
    <div className="simulator-slider-head"><label htmlFor={id}>{label}</label><output htmlFor={id}>{valueLabel}</output></div>
    <input id={id} type="range" min={min} max={max} step={step} value={value} aria-valuetext={valueLabel} onChange={event => onChange(Number(event.target.value))} />
    <div className="simulator-slider-scale"><span>{minLabel}</span><span>{maxLabel}</span></div>
  </div>;
}

function scenarioMoney(amount: number, currency: Currency): string {
  const amountMinor = majorToMinor(amount, currency, { allowNegative: true });
  return amountMinor == null ? 'N/A' : formatMoney({ amount_minor: amountMinor, currency }, { allowNegative: true });
}

function AllocationMeter({ label, value, max, detail }: { label: string; value: number; max: number; detail: string }) {
  return <div className="simulator-meter">
    <div className="simulator-meter-head"><b>{label}</b><span>{detail}</span></div>
    <progress value={value} max={Math.max(1, max)} aria-label={label} />
  </div>;
}

export function StrategyRoiSimulator({ accounts, cases, capacity }: { accounts: AccountRecord[]; cases: DecisionCase[]; capacity: Capacity }) {
  const [scenarioCurrency, setScenarioCurrency] = useState<Currency>(() => capacity.budgets[0]?.currency ?? 'MYR');
  const [scenarioBudget, setScenarioBudget] = useState(() => Math.round(minorToMajor(capacity.budgets[0]) ?? 500));
  const [scenarioCapacity, setScenarioCapacity] = useState(() => capacity.review_slots);
  const [strategy, setStrategy] = useState<Strategy>('exposure');
  const [scenarioCaseId, setScenarioCaseId] = useState('');
  const [scenarioActionId, setScenarioActionId] = useState('');
  const [scenarioCost, setScenarioCost] = useState<number | null>(null);
  const [margin, setMargin] = useState(70);
  const [assumedReduction, setAssumedReduction] = useState(10);

  const byId = new Map(accounts.map(account => [account.customer_id, account]));
  const budgetLimit = capacity.budgets.find(value => value.currency === scenarioCurrency);
  const budgetLimitMajor = minorToMajor(budgetLimit) ?? 0;
  const budgetMax = Math.max(1000, Math.ceil(budgetLimitMajor * 2 / 100) * 100);
  const capacityMax = Math.max(10, capacity.review_slots * 2);

  const candidates: Candidate[] = cases.flatMap(item => {
    const account = byId.get(item.customer_id);
    if (!account || account.mrr?.currency !== scenarioCurrency || !['PRIORITY_REVIEW', 'HUMAN_REVIEW'].includes(item.route)
      || !['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)
      || account.prediction?.status !== 'scored' || account.prediction.p_churn_30d == null) return [];
    const action = proposalsFor(item).find(proposal => proposal.eligible && proposal.id !== 'NO_INTERVENTION'
      && proposal.estimated_cost?.currency === scenarioCurrency && proposal.estimated_cost.amount_minor >= 0);
    return action ? [{ item, account, action }] : [];
  });
  const scenarioCandidates = strategy === 'exposure'
    ? candidates.filter(candidate => candidate.account.exposure_proxy?.currency === scenarioCurrency)
    : candidates;
  const sortedCandidates = [...scenarioCandidates].sort((left, right) => {
    const leftValue = strategy === 'risk' ? left.account.prediction?.p_churn_30d ?? -1 : left.account.exposure_proxy?.amount_minor ?? -1;
    const rightValue = strategy === 'risk' ? right.account.prediction?.p_churn_30d ?? -1 : right.account.exposure_proxy?.amount_minor ?? -1;
    return rightValue - leftValue || left.account.customer_id.localeCompare(right.account.customer_id);
  });
  const budgetMinor = majorToMinor(scenarioBudget, scenarioCurrency) ?? 0;
  let budgetRemaining = budgetMinor;
  const allocated: Candidate[] = [];
  for (const candidate of sortedCandidates) {
    if (allocated.length >= scenarioCapacity) break;
    const cost = candidate.action.estimated_cost?.amount_minor;
    if (cost == null || cost > budgetRemaining) continue;
    allocated.push(candidate);
    budgetRemaining -= cost;
  }
  const spentMinor = budgetMinor - budgetRemaining;

  const roiCases = cases.filter(item => {
    const account = byId.get(item.customer_id);
    return account?.prediction?.status === 'scored' && (account.prediction.p_churn_30d ?? 0) > 0
      && (minorToMajor(account.mrr) ?? 0) > 0
      && proposalsFor(item).some(action => action.eligible && action.id !== 'NO_INTERVENTION'
        && action.estimated_cost?.currency === account.mrr?.currency && (minorToMajor(action.estimated_cost) ?? 0) > 0);
  });
  const roiCase = roiCases.find(item => item.id === scenarioCaseId) ?? roiCases[0];
  const roiAccount = roiCase ? byId.get(roiCase.customer_id) : undefined;
  const roiActions = roiCase ? proposalsFor(roiCase).filter(action => action.eligible && action.id !== 'NO_INTERVENTION'
    && action.estimated_cost?.currency === roiAccount?.mrr?.currency && (minorToMajor(action.estimated_cost) ?? 0) > 0) : [];
  const roiAction = roiActions.find(action => action.id === scenarioActionId)
    ?? roiActions.find(action => action.id === roiCase?.proposed_action) ?? roiActions[0];
  const roiCurrency = roiAccount?.mrr?.currency;
  const proposalCost = minorToMajor(roiAction?.estimated_cost);
  const actionCost = scenarioCost ?? proposalCost;
  const costMax = Math.max(100, Math.ceil((proposalCost ?? 0) * 2 / 50) * 50);
  const baselineRisk = roiAccount?.prediction?.p_churn_30d ?? null;
  const reductionMax = baselineRisk == null ? 100 : baselineRisk * 100;
  const effectiveReduction = Math.min(assumedReduction, reductionMax);
  const roiResult = calculateScenario({
    mrr: minorToMajor(roiAccount?.mrr), p30: baselineRisk, margin: margin / 100,
    cost: actionCost ?? 0, assumed_reduction: effectiveReduction / 100,
  });

  return <div className="simulator-page">
    <section className="simulator-heading">
      <div><span className="pill amber">SCENARIO ONLY</span><h2>Strategy &amp; ROI simulator</h2><p className="muted">Move the sliders to explore a hypothetical review plan and one-month break-even case.</p></div>
      <span className="pill neutral">Demo fixture · no backend allocation</span>
    </section>

    <div className="simulator-layout">
      <section className="card simulator-controls" aria-labelledby="allocation-controls-title">
        <div className="section-head"><div><small className="simulator-step">01 · ALLOCATION</small><h2 id="allocation-controls-title">Set review resources</h2></div></div>
        <div className="simulator-selects">
          <label>Budget currency<select value={scenarioCurrency} onChange={event => {
            const nextCurrency = event.target.value;
            setScenarioCurrency(nextCurrency);
            setScenarioBudget(Math.round(minorToMajor(capacity.budgets.find(value => value.currency === nextCurrency)) ?? 500));
          }}>{capacity.budgets.map(value => <option key={value.currency} value={value.currency}>{value.currency}</option>)}</select></label>
          <label>Prioritize by<select value={strategy} onChange={event => setStrategy(event.target.value as Strategy)}><option value="exposure">MRR-weighted exposure</option><option value="risk">30-day risk probability</option></select></label>
        </div>
        <ScenarioSlider id="scenario-budget" label="Scenario budget" min={0} max={budgetMax} step={10}
          value={scenarioBudget} valueLabel={scenarioMoney(scenarioBudget, scenarioCurrency)}
          minLabel={scenarioMoney(0, scenarioCurrency)} maxLabel={scenarioMoney(budgetMax, scenarioCurrency)} onChange={setScenarioBudget} />
        <ScenarioSlider id="scenario-capacity" label="Review slots" min={0} max={capacityMax} step={1}
          value={scenarioCapacity} valueLabel={`${scenarioCapacity} slots`} minLabel="0 slots" maxLabel={`${capacityMax} slots`} onChange={setScenarioCapacity} />
        <p className="caption">These sliders change only the scenario. Actual review capacity and budgets are not updated.</p>
      </section>

      <section className="card simulator-output" aria-live="polite" aria-labelledby="allocation-results-title">
        <div className="section-head"><div><small className="simulator-step">LIVE RESULT</small><h2 id="allocation-results-title">Allocation preview</h2></div></div>
        <div className="simulator-result-hero"><strong>{allocated.length}<span> / {scenarioCandidates.length}</span></strong><p>eligible cases fit this budget and capacity</p></div>
        <AllocationMeter label="Budget used" value={spentMinor} max={budgetMinor}
          detail={`${formatMoney({ amount_minor: spentMinor, currency: scenarioCurrency })} of ${formatMoney({ amount_minor: budgetMinor, currency: scenarioCurrency })}`} />
        <AllocationMeter label="Review slots used" value={allocated.length} max={scenarioCapacity}
          detail={`${allocated.length} of ${scenarioCapacity} slots`} />
        <div className="simulator-summary"><div><small>Unallocated budget</small><b>{formatMoney({ amount_minor: budgetRemaining, currency: scenarioCurrency })}</b></div><div><small>Slots remaining</small><b>{Math.max(0, scenarioCapacity - allocated.length)}</b></div></div>
        <p className="caption">Candidate costs and MRR are compared within {scenarioCurrency}. The selected heuristic is a fixture what-if, not the backend decision rank.</p>
      </section>
    </div>

    <section className="card simulator-candidates">
      <div className="section-head"><div><h2>Cases in the scenario</h2><p className="muted">The allocation updates as the resource sliders move.</p></div><span className="pill neutral">{sortedCandidates.length} candidates</span></div>
      {sortedCandidates.length ? <div className="tablewrap"><table><thead><tr><th>Rank</th><th>Account / case</th><th>p30</th><th>Exposure proxy</th><th>Eligible action</th><th>Estimated cost</th><th>Scenario result</th></tr></thead><tbody>
        {sortedCandidates.map((candidate, index) => <tr key={candidate.item.id}><td>#{index + 1}</td><td>{candidate.account.customer_id}<small>{candidate.item.id}</small></td><td>{formatRisk(candidate.account.prediction, 30)}</td><td>{formatMoney(candidate.account.exposure_proxy)}</td><td>{candidate.action.id.replaceAll('_', ' ').toLowerCase()}</td><td>{formatMoney(candidate.action.estimated_cost)}</td><td><span className={`pill ${allocated.includes(candidate) ? 'good' : 'neutral'}`}>{allocated.includes(candidate) ? 'Fits plan' : 'Not allocated'}</span></td></tr>)}
      </tbody></table></div> : <p className="empty-trend">No eligible cases with an action cost in {scenarioCurrency} are available for this strategy.</p>}
      <p className="caption">This list follows the shared account search and currency filters. Revenue Captured @K and strategy performance are unavailable without historical replay and mature outcomes.</p>
    </section>

    <div className="simulator-layout">
      <section className="card simulator-controls" aria-labelledby="roi-controls-title">
        <div className="section-head"><div><small className="simulator-step">02 · BREAK-EVEN</small><h2 id="roi-controls-title">Set ROI assumptions</h2></div><span className="pill amber">SCENARIO ONLY</span></div>
        {roiCases.length === 0 ? <p className="empty-trend">No case has valid MRR, p30, and an eligible action cost in this fixture.</p> : <>
          <div className="simulator-selects">
            <label>Case<select value={roiCase?.id ?? ''} onChange={event => { setScenarioCaseId(event.target.value); setScenarioActionId(''); setScenarioCost(null); }}>{roiCases.map(item => <option key={item.id} value={item.id}>{item.customer_id} · {item.id}</option>)}</select></label>
            <label>Eligible action<select value={roiAction?.id ?? ''} onChange={event => { setScenarioActionId(event.target.value); setScenarioCost(null); }}>{roiActions.map(action => <option key={action.id} value={action.id}>{action.id.replaceAll('_', ' ').toLowerCase()}</option>)}</select></label>
          </div>
          <div className="simulator-context"><span>MRR <b>{formatMoney(roiAccount?.mrr)}</b></span><span>Baseline p30 <b>{formatRisk(roiAccount?.prediction ?? null, 30)}</b></span><span>Proposal cost <b>{formatMoney(roiAction?.estimated_cost)}</b></span></div>
          <ScenarioSlider id="scenario-action-cost" label="Assumed action cost" min={0} max={costMax} step={1}
            value={actionCost ?? 0} valueLabel={roiCurrency ? scenarioMoney(actionCost ?? 0, roiCurrency) : 'N/A'}
            minLabel={roiCurrency ? scenarioMoney(0, roiCurrency) : 'N/A'} maxLabel={roiCurrency ? scenarioMoney(costMax, roiCurrency) : 'N/A'}
            onChange={setScenarioCost} />
          <ScenarioSlider id="scenario-margin" label="Contribution margin" min={0} max={100} step={1}
            value={margin} valueLabel={`${margin}%`} minLabel="0%" maxLabel="100%" onChange={setMargin} />
          <ScenarioSlider id="scenario-reduction" label="Assumed absolute churn reduction" min={0} max={reductionMax} step={0.1}
            value={effectiveReduction} valueLabel={`${effectiveReduction.toFixed(1)} pp`}
            minLabel="0 pp" maxLabel={`${reductionMax.toFixed(1)} pp`}
            onChange={value => setAssumedReduction(Math.min(value, reductionMax))} />
          <p className="caption">Action cost, margin, and reduction are editable assumptions. A percentage-point reduction differs from a relative share of baseline risk.</p>
        </>}
      </section>

      <section className="card simulator-output" aria-live="polite" aria-labelledby="roi-results-title">
        <div className="section-head"><div><small className="simulator-step">LIVE RESULT</small><h2 id="roi-results-title">Break-even result</h2></div></div>
        {roiResult && roiCurrency ? <>
          <div className="simulator-result-hero"><strong className={roiResult.net_value < 0 ? 'negative' : undefined}>{scenarioMoney(roiResult.net_value, roiCurrency)}</strong><p>hypothetical one-month net value</p></div>
          <div className="simulator-summary"><div><small>Scenario gross value</small><b>{scenarioMoney(roiResult.gross_value, roiCurrency)}</b></div><div><small>Assumed action cost</small><b>{scenarioMoney(actionCost ?? 0, roiCurrency)}</b></div><div><small>Break-even reduction</small><b>{(roiResult.break_even_reduction * 100).toFixed(2)} pp</b></div><div><small>Share of baseline risk</small><b>{(roiResult.break_even_share * 100).toFixed(1)}%</b></div><div><small>Scenario ROI</small><b>{(roiResult.roi * 100).toFixed(1)}%</b></div></div>
          <div className="simulator-threshold"><div><span>Assumed reduction</span><b>{effectiveReduction.toFixed(1)} pp</b></div><div className="simulator-threshold-track" role="img" aria-label={`Assumed reduction ${effectiveReduction.toFixed(1)} percentage points; break-even ${(roiResult.break_even_reduction * 100).toFixed(2)} percentage points`}><span style={{ width: `${baselineRisk ? Math.min(100, effectiveReduction / (baselineRisk * 100) * 100) : 0}%` }} /><i style={{ left: `${Math.min(100, roiResult.break_even_share * 100)}%` }} /></div><small>{roiResult.impossible ? 'Break-even exceeds baseline churn risk.' : 'Marker shows the break-even point within baseline risk.'}</small></div>
        </> : <p className="empty-trend">Enter a positive action cost and contribution margin for a valid scenario. Source-backed effectiveness is not available.</p>}
        <p className="caption">Scenario arithmetic is not observed savings, causal uplift, or measured ROI.</p>
      </section>
    </div>
  </div>;
}
