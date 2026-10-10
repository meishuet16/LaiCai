import assert from 'node:assert/strict';
import test from 'node:test';
import { feedbackAt, visibleTimelineEvents } from './timeline.ts';
import { fixtureTimelineService } from '../services/timelineService.ts';

test('historical cutoff hides events that occurred or became available later', async () => {
  const record = await fixtureTimelineService.getTimeline('c02');
  assert.ok(record);
  const atCutoff = visibleTimelineEvents(record.events, '2026-10-10T00:00:00Z');
  assert.ok(atCutoff.some(event => event.id === 'demo_src_c02_usage'));
  assert.ok(!atCutoff.some(event => event.id === 'demo_src_c02_late'));
  assert.ok(!atCutoff.some(event => event.category === 'prediction'));
  const afterReceipt = visibleTimelineEvents(record.events, '2026-10-10T01:01:00Z');
  assert.ok(afterReceipt.some(event => event.id === 'demo_src_c02_late'));
  assert.ok(!afterReceipt.some(event => event.category === 'prediction'));
});

test('feedback uses prediction as-of and never invents mature negatives', async () => {
  const record = await fixtureTimelineService.getTimeline('c02');
  assert.ok(record);
  assert.equal(feedbackAt(record.account, 7, null), null);
  assert.equal(feedbackAt(record.account, 7, '2026-10-10T00:01:00Z'), null);
});

test('known cancellation is ineligible and unknown accounts have no timeline', async () => {
  const known = await fixtureTimelineService.getTimeline('c06');
  assert.ok(known);
  assert.equal(feedbackAt(known.account, 30, '2026-10-10T00:01:00Z'), null);
  assert.equal(await fixtureTimelineService.getTimeline('missing'), null);
});

test('timeline source fixtures are redacted and case history is not linked to current prediction', async () => {
  const record = await fixtureTimelineService.getTimeline('c01');
  assert.ok(record);
  assert.ok(record.events.filter(event => event.category === 'source').every(event => event.source_record_id && !event.summary.includes('@')));
  assert.ok(record.events.filter(event => event.category === 'decision').every(event => event.prediction_id === null));
});

test('older case workflow remains before the current prediction, without retroactive linkage', async () => {
  const record = await fixtureTimelineService.getTimeline('c03');
  assert.ok(record);
  assert.deepEqual(visibleTimelineEvents(record.events, null), []);
  const ordered = visibleTimelineEvents(record.events, '2026-10-31T00:00:00Z');
  const route = ordered.findIndex(event => event.id === 'demo_audit_c03_1');
  const action = ordered.findIndex(event => event.id.startsWith('demo_action_c03_'));
  assert.ok(route >= 0 && action > route);
  assert.equal(ordered[action].prediction_id, null);
});
