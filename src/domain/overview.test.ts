import assert from 'node:assert/strict';
import test from 'node:test';
import { summarizeOverview } from './overview.ts';
import { decisionService } from '../services/decisionService.ts';
import { integrationService } from '../services/integrationService.ts';
import { retainIQService } from '../services/retainIQService.ts';

async function getSummary(horizon: 7 | 14 | 30) {
  decisionService.resetDemo();
  const [accounts, cases, integration] = await Promise.all([retainIQService.listAccounts(), decisionService.listCases(), integrationService.getOverview()]);
  const asOf = accounts.find(account => account.prediction)?.prediction?.as_of;
  assert.ok(asOf);
  return summarizeOverview(accounts, cases, integration, asOf, horizon);
}

test('overview reports distinct forecast, workload, freshness and currency-separated exposure values', async () => {
  const summary = await getSummary(30);
  assert.equal(summary.eligibleAccounts, 7);
  assert.equal(summary.validPredictions, 6);
  assert.equal(summary.openCases, 6);
  assert.equal(summary.pendingCases, 4);
  assert.equal(summary.overdueCases, 1);
  assert.equal(summary.knownCancellations, 1);
  assert.equal(summary.abstained, 1);
  assert.equal(summary.insufficientEvidence, 2);
  assert.equal(summary.riskCounts.low, 1);
  assert.equal(summary.riskCounts.medium, 3);
  assert.equal(summary.riskCounts.high, 2);
  assert.equal(summary.exposureByCurrency.MYR?.amount_minor, 105400);
  assert.equal(summary.exposureByCurrency.SGD?.amount_minor, 120000);
  assert.equal(summary.exposureAccountCount, 4);
  assert.equal(summary.myrReportedMrr?.amount_minor, 313000);
  assert.equal(summary.myrAccountCount, 6);
  assert.equal(summary.sgdAccountCount, 1);
  assert.equal(summary.missingMrr, 2);
  assert.deepEqual(summary.sourceFreshness, { fresh: 2, stale: 1, unknown: 0 });
});

test('changing horizon recomputes bands from stored horizon outputs without deriving probabilities', async () => {
  const summary = await getSummary(7);
  assert.equal(summary.validPredictions, 6);
  assert.equal(summary.riskCounts.low, 4);
  assert.equal(summary.riskCounts.medium, 2);
  assert.equal(summary.riskCounts.high, 0);
});

test('priority preview preserves service order and activity uses dated audit or sanitized rejection records', async () => {
  const summary = await getSummary(30);
  assert.deepEqual(summary.priorityCases.map(item => item.customer_id), ['c01', 'c02', 'c03', 'c08']);
  assert.equal(summary.recentActivity[0].title, 'Rejected source record');
  assert.equal(summary.recentActivity[0].detail.includes('identifiers redacted'), false);
  assert.equal(summary.recentActivity.some(item => item.title === 'Prediction outputs available'), true);
  assert.equal(summary.recentActivity.some(item => item.title === 'Decision route recorded'), true);
});
