import assert from 'node:assert/strict';
import test from 'node:test';
import { fixtureDataSource } from './retainIQService.ts';

test('fixture forecasts preserve identity, cumulative horizons, and currency', async () => {
  const accounts = await fixtureDataSource.listAccounts();
  for (const account of accounts) {
    const prediction = account.prediction;
    assert.ok(prediction);
    assert.equal(prediction.customer_id, account.customer_id);
    if (prediction.status === 'scored') {
      assert.ok(prediction.p_churn_7d != null && prediction.p_churn_14d != null && prediction.p_churn_30d != null);
      assert.ok(prediction.p_churn_7d <= prediction.p_churn_14d);
      assert.ok(prediction.p_churn_14d <= prediction.p_churn_30d);
    } else {
      assert.equal(prediction.p_churn_7d, null);
      assert.equal(prediction.p_churn_14d, null);
      assert.equal(prediction.p_churn_30d, null);
    }
    if (account.exposure_proxy) assert.equal(account.exposure_proxy.currency, account.mrr?.currency);
  }
  assert.equal(accounts.find(account => account.customer_id === 'c04')?.exposure_proxy, null);
  assert.equal(accounts.find(account => account.customer_id === 'c07')?.mrr, null);
  assert.equal(accounts.find(account => account.customer_id === 'c06')?.route, 'KNOWN_CANCELLATION');
});

test('missing account remains missing', async () => {
  assert.equal(await fixtureDataSource.getAccount('unknown'), null);
  assert.equal(await fixtureDataSource.getPrediction('unknown'), null);
  assert.equal((await fixtureDataSource.getPrediction('demo_pred_c02'))?.customer_id, 'c02');
});
