import assert from 'node:assert/strict';
import test from 'node:test';
import { fixtureIntegrationService, integrationDataSource } from './integrationService.ts';

test('integration fixtures preserve source timing and redact rejected metadata', async () => {
  const overview = await fixtureIntegrationService.getOverview();
  assert.equal(overview.evidence_kind, 'demo_fixture');
  for (const source of overview.sources) {
    assert.ok(source.latest_occurred_at);
    assert.ok(source.latest_available_at);
    assert.ok(source.mapping_version);
    assert.equal('schema_version' in source, false);
    assert.equal('sensitivity' in source, false);
    assert.equal('provenance' in source, false);
  }
  for (const rejected of overview.rejected_events) {
    assert.match(rejected.redacted_metadata, /redacted/);
    assert.equal('payload' in rejected, false);
  }
  assert.equal('accounts_quarantined' in overview.coverage, false);
});

test('connected mode never silently falls back to integration fixtures', async () => {
  const originalFetch = globalThis.fetch;
  const backendOverview = { evidence_kind: 'source_backed', sources: [], coverage: { accounts_mapped: 30, accounts_unmatched: 0, active_paying: 24, missing_mrr: 4, incomplete_subscription_history: 3, usage_percent: 96, billing_percent: 91, subscription_percent: 99 }, rejected_events: [], alerts: [] };
  globalThis.fetch = (async () => new Response(JSON.stringify(backendOverview), { status: 200, headers: { 'Content-Type': 'application/json' } })) as typeof fetch;
  try {
    const connected = await integrationDataSource('connected').getOverview();
    assert.equal(connected.evidence_kind, 'source_backed');
    assert.deepEqual(connected.sources, []);
    assert.deepEqual(connected.coverage, backendOverview.coverage);
    assert.equal(await integrationDataSource('demo_fixture').getOverview().then(value => value.evidence_kind), 'demo_fixture');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('integration fixture vocabulary uses canonical event names only', async () => {
  const overview = await fixtureIntegrationService.getOverview();
  const eventTypes = overview.sources.flatMap(source => source.event_types);
  assert.ok(eventTypes.includes('subscription_created'));
  assert.ok(eventTypes.includes('subscription_cancelled_effective'));
  assert.ok(eventTypes.includes('invoice_payment_failed'));
  assert.ok(eventTypes.includes('usage_aggregate_updated'));
  assert.ok(!eventTypes.includes('subscription_started' as never));
});
