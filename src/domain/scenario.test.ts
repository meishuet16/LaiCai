import assert from 'node:assert/strict';
import test from 'node:test';
import { calculateScenario } from './scenario.ts';

test('scenario uses absolute percentage-point reduction and one-month contribution', () => {
  const result = calculateScenario({ mrr: 1200, p30: .65, margin: .7, cost: 150, assumed_reduction: .1 });
  assert.ok(result);
  assert.ok(Math.abs(result.break_even_reduction - 150 / 840) < 1e-10);
  assert.ok(Math.abs(result.break_even_share - (150 / 840) / .65) < 1e-10);
  assert.equal(result.gross_value, 84);
  assert.equal(result.net_value, -66);
  assert.equal(result.roi, -.44);
  assert.equal(result.impossible, false);
});
test('missing and invalid inputs are N/A; impossible break-even is flagged', () => {
  assert.equal(calculateScenario({ mrr: null, p30: .5, margin: .7, cost: 10, assumed_reduction: .1 }), null);
  assert.equal(calculateScenario({ mrr: 1200, p30: .5, margin: .7, cost: 0, assumed_reduction: .1 }), null);
  assert.equal(calculateScenario({ mrr: 1200, p30: .5, margin: .7, cost: 10, assumed_reduction: .6 }), null);
  assert.equal(calculateScenario({ mrr: 100, p30: .1, margin: .5, cost: 20, assumed_reduction: .05 })?.impossible, true);
});
