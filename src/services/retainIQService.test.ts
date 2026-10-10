import assert from 'node:assert/strict';
import test from 'node:test';
import { accountDataSource, connectedDataSource, fixtureDataSource, NotConnectedError } from './retainIQService.ts';

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

test('fixture and connected sources remain separate; connected mode reports the missing contract', async () => {
  await assert.rejects(() => connectedDataSource.listAccounts(), NotConnectedError);
  await assert.rejects(() => accountDataSource('connected').listAccounts(), NotConnectedError);
  assert.equal((await accountDataSource('demo_fixture').listAccounts()).length, 9);
});

test('demo fixtures retain sample names and owners without inventing tenant, cutoff, or model metadata', async () => {
  const accounts = await fixtureDataSource.listAccounts();
  assert.equal(accounts.find(account => account.customer_id === 'c01')?.name, 'Northwind Logistics');
  assert.equal(accounts.find(account => account.customer_id === 'c01')?.owner, 'Janice');
  assert.equal(accounts.find(account => account.customer_id === 'c02')?.name, 'Kopi Ventures');
  for (const account of accounts) {
    assert.ok(account.name);
    assert.equal(account.tenant_id, null);
    assert.equal(account.prediction?.tenant_id, null);
    assert.equal(account.prediction?.as_of, null);
    assert.equal(account.prediction?.model_version, null);
    assert.equal(account.evidence_kind, 'demo_fixture');
  }
});
