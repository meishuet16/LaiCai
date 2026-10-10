import assert from 'node:assert/strict';
import test from 'node:test';
import { integrationService } from './integrationService.ts';

test('integration fixtures preserve source timing and redact rejected metadata', async () => {
  const overview = await integrationService.getOverview();
  assert.equal(overview.evidence_kind, 'synthetic');
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
