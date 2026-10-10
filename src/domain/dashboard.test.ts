import assert from 'node:assert/strict';
import test from 'node:test';
import { selectDashboardRows, summarizeDashboard } from './dashboard.ts';
import { decisionService } from '../services/decisionService.ts';
import { retainIQService } from '../services/retainIQService.ts';

const filters = { horizon: 30 as const, route: 'all' as const, actionStatus: 'all' as const, actionType: 'all' as const, owner: 'all', segment: 'all', currency: 'All' as const, query: '' };

test('dashboard aggregates the linked demo cohort, not source-health population totals', async () => {
  decisionService.resetDemo();
  const [accounts, cases] = await Promise.all([retainIQService.listAccounts(), decisionService.listCases()]);
  const summary = summarizeDashboard(selectDashboardRows(accounts, cases, filters), 30);
  assert.equal(summary.rows.length, 9);
  assert.equal(summary.eligible, 7);
  assert.equal(summary.scored, 6);
  assert.equal(summary.abstained, 1);
  assert.equal(summary.ineligible, 1);
  assert.equal(summary.routeCounts.PRIORITY_REVIEW, 4);
  assert.equal(summary.pending, 4);
  assert.equal(summary.overdue, 1);
  assert.equal(summary.followUpsDue, 1);
  assert.equal(summary.missingMrr, 1);
});

test('exposure, cost and actuals remain currency-separated with missing actuals flagged', async () => {
  decisionService.resetDemo();
  const [accounts, cases] = await Promise.all([retainIQService.listAccounts(), decisionService.listCases()]);
  const summary = summarizeDashboard(selectDashboardRows(accounts, cases, filters), 30);
  assert.deepEqual(summary.exposureByCurrency, [{ currency: 'MYR', amount_minor: 105400 }, { currency: 'SGD', amount_minor: 120000 }]);
  assert.deepEqual(summary.estimatedCostByCurrency, [{ currency: 'MYR', amount_minor: 19000 }, { currency: 'SGD', amount_minor: 0 }]);
  assert.deepEqual(summary.actualCostByCurrency, [{ currency: 'MYR', amount_minor: 3500 }, { currency: 'SGD', amount_minor: 0 }]);
  assert.equal(summary.missingActualCost, 1);
  assert.equal(summary.missingActualMinutes, 1);
});

test('filters and 7-day bands recompute from the selected cohort', async () => {
  decisionService.resetDemo();
  const [accounts, cases] = await Promise.all([retainIQService.listAccounts(), decisionService.listCases()]);
  const rows = selectDashboardRows(accounts, cases, { ...filters, route: 'PRIORITY_REVIEW', currency: 'SGD' });
  assert.deepEqual(rows.map(row => row.account.customer_id), ['c08']);
  const summary = summarizeDashboard(rows, 7);
  assert.equal(summary.riskBands.find(item => item.band === 'low')?.count, 1);
  assert.equal(summary.exposureByCurrency.find(item => item.currency === 'MYR')?.amount_minor, 0);
});
