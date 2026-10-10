import type { Freshness, Reliability } from '../domain/customer';

export type RiskBand = 'low' | 'medium' | 'high' | 'no_score' | null;
const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());

export function RiskPill({ band }: { band: RiskBand }) {
  return <span className={`pill risk-pill risk-${band ?? 'no_score'}`}>{band === 'no_score' ? 'No score' : band ? label(band) : 'Policy band unavailable'}</span>;
}

export function EvidencePills({ reliability, freshness, compact = false }: { reliability?: Reliability | null; freshness?: Freshness | null; compact?: boolean }) {
  const reliabilityTone = reliability === 'sufficient_evidence' ? 'good' : reliability === 'limited_evidence' ? 'amber' : reliability === 'insufficient_evidence' ? 'red' : 'neutral';
  const freshnessTone = freshness === 'fresh' ? 'good' : freshness === 'partially_stale' ? 'amber' : freshness === 'stale' ? 'red' : 'neutral';
  const reliabilityLabel = compact ? reliability === 'sufficient_evidence' ? 'Sufficient' : reliability === 'limited_evidence' ? 'Limited' : reliability === 'insufficient_evidence' ? 'Insufficient' : 'Unknown' : label(reliability ?? 'unknown');
  const freshnessLabel = compact ? freshness === 'fresh' ? 'Fresh' : freshness === 'partially_stale' ? 'Partial' : freshness === 'stale' ? 'Stale' : 'Unknown' : `${label(freshness ?? 'unknown')} data`;
  return <span className={`evidence-pills${compact ? ' compact' : ''}`}><span className={`pill ${reliabilityTone}`} title={`${label(reliability ?? 'unknown')}: evidence sufficiency; not probability of correctness`}>{reliabilityLabel}</span><span className={`pill ${freshnessTone}`} title={`${label(freshness ?? 'unknown')} data`}>{freshnessLabel}</span></span>;
}
