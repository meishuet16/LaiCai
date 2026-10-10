import type { Freshness, Reliability } from '../domain/customer';

export type RiskBand = 'low' | 'medium' | 'high' | 'no_score';
const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());

export function RiskPill({ band }: { band: RiskBand }) {
  return <span className={`pill risk-pill risk-${band}`}>{band === 'no_score' ? 'No score' : label(band)}</span>;
}

export function EvidencePills({ reliability, freshness }: { reliability?: Reliability | null; freshness?: Freshness | null }) {
  const reliabilityTone = reliability === 'sufficient_evidence' ? 'good' : reliability === 'limited_evidence' ? 'amber' : reliability === 'insufficient_evidence' ? 'red' : 'neutral';
  const freshnessTone = freshness === 'fresh' ? 'good' : freshness === 'partially_stale' ? 'amber' : freshness === 'stale' ? 'red' : 'neutral';
  return <span className="evidence-pills"><span className={`pill ${reliabilityTone}`} title="Evidence sufficiency; not probability of correctness">{label(reliability ?? 'unknown')}</span><span className={`pill ${freshnessTone}`}>{label(freshness ?? 'unknown')} data</span></span>;
}
