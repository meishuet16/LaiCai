export type ScenarioInput = { mrr: number | null; p30: number | null; margin: number; cost: number; assumed_reduction: number };
export type ScenarioResult = { break_even_reduction: number; break_even_share: number; gross_value: number; net_value: number; roi: number; impossible: boolean };

// Amounts share one currency and use major units. This is an assumption-only, one-month illustration.
export function calculateScenario(input: ScenarioInput): ScenarioResult | null {
  const { mrr, p30, margin, cost, assumed_reduction } = input;
  if (mrr == null || p30 == null || ![mrr, p30, margin, cost, assumed_reduction].every(Number.isFinite) || mrr <= 0 || p30 <= 0 || p30 > 1 || margin <= 0 || margin > 1 || cost <= 0 || assumed_reduction < 0 || assumed_reduction > p30) return null;
  const contribution = mrr * margin;
  const break_even_reduction = cost / contribution;
  const gross_value = assumed_reduction * contribution;
  return { break_even_reduction, break_even_share: break_even_reduction / p30, gross_value, net_value: gross_value - cost, roi: (gross_value - cost) / cost, impossible: break_even_reduction > p30 };
}
