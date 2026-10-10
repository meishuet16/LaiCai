import assert from 'node:assert/strict';
import test from 'node:test';
import { summarizeOverview } from './overview.ts';
import { decisionService } from '../services/decisionService.ts';
import { fixtureIntegrationService } from '../services/integrationService.ts';
import { retainIQService } from '../services/retainIQService.ts';

async function getSummary(horizon: 7 | 14 | 30) {
  decisionService.resetDemo();
  const [accounts, cases, integration] = await Promise.all([retainIQService.listAccounts(), decisionService.listCases(), fixtureIntegrationService.getOverview()]);
  return summarizeOverview(accounts, cases, integration, null, horizon);
}

test('overview reports distinct forecast, workload, freshness and currency-separated exposure values', async () => {
  const summary = await getSummary(30);
  assert.equal(summary.eligibleAccounts, 7);
  assert.equal(summary.validPredictions, 6);
  assert.equal(summary.openCases, 6);
  assert.equal(summary.pendingCases, 4);
  assert.equal(summary.overdueCases, null);
  assert.equal(summary.knownCancellations, 1);
  assert.equal(summary.abstained, 1);
  assert.equal(summary.insufficientEvidence, 2);
  assert.deepEqual(summary.predictionStatuses, { scored: 6, abstained: 1, known_cancellation: 1, not_eligible: 1 });
  assert.equal(summary.exposureByCurrency.MYR?.amount_minor, 105400);
  assert.equal(summary.exposureByCurrency.SGD?.amount_minor, 120000);
  assert.equal(summary.exposureAccountCount, 4);
  assert.equal(summary.mrrByCurrency.MYR?.amount_minor, 313000);
  assert.equal(summary.mrrAccountCounts.MYR, 6);
  assert.equal(summary.mrrByCurrency.SGD?.amount_minor, 240000);
  assert.equal(summary.missingMrr, 2);
  assert.deepEqual(summary.sourceFreshness, { fresh: 2, stale: 1, unknown: 0 });
});

test('changing horizon recomputes bands from stored horizon outputs without deriving probabilities', async () => {
  const summary = await getSummary(7);
  assert.equal(summary.validPredictions, 6);
  assert.equal(summary.validPredictions, 6);
});

test('priority preview preserves service order and activity uses dated audit or sanitized rejection records', async () => {
  const summary = await getSummary(30);
  assert.deepEqual(summary.priorityCases.map(item => item.customer_id), ['c01', 'c02', 'c03', 'c08']);
  assert.equal(summary.recentActivity.some(item => item.title === 'Rejected source record'), false);
  assert.equal(summary.recentActivity.some(item => item.detail.includes('identifiers redacted')), false);
  assert.equal(summary.recentActivity.some(item => item.title === 'Prediction outputs available'), false);
  assert.equal(summary.recentActivity.some(item => item.title === 'Decision route recorded'), true);
});
