import assert from 'node:assert/strict';
import test from 'node:test';
import { accountDataSource, connectedDataSource, fixtureDataSource } from './retainIQService.ts';

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

test('fixture and connected sources remain separate; connected mode uses the backend adapter', async () => {
  const originalFetch = globalThis.fetch;
  const fixture = structuredClone((await fixtureDataSource.listAccounts())[0]);
  fixture.tenant_id = 'tenant-01';
  fixture.evidence_kind = 'source_backed';
  fixture.data_origin = 'backend_dataset';
  fixture.prediction!.tenant_id = 'tenant-01';
  fixture.prediction!.as_of = '2026-10-01T00:00:00Z';
  fixture.prediction!.generated_at = '2026-10-01T00:05:00Z';
  fixture.prediction!.model_version = 'synthetic_demo_model_v1';
  globalThis.fetch = (async (input) => {
    const url = String(input);
    if (url.endsWith('/v1/dashboard/accounts')) return new Response(JSON.stringify({ accounts: [fixture], meta: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    if (url.endsWith('/v1/decisions/route')) return new Response(JSON.stringify({ customer_id: fixture.customer_id, prediction_id: fixture.prediction!.prediction_id, route: 'PRIORITY_REVIEW', route_reason: 'backend_policy', exposure_proxy_30d_minor: 62400, currency: 'MYR' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    return new Response(null, { status: 404 });
  }) as typeof fetch;
  try {
    const connected = await connectedDataSource.listAccounts();
    assert.equal(connected.length, 1);
    assert.equal(connected[0].data_origin, 'backend_dataset');
    assert.equal(connected[0].route_reason, 'backend_policy');
    assert.equal((await accountDataSource('connected').listAccounts()).length, 1);
    assert.equal((await accountDataSource('demo_fixture').listAccounts()).length, 9);
  } finally {
    globalThis.fetch = originalFetch;
  }
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
