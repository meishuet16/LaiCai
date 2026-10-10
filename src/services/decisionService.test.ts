import assert from 'node:assert/strict';
import test from 'node:test';
import { decisionService, getCapacity, proposalsFor } from './decisionService.ts';

test('routes include all five queues and quality cases allow only investigation', async () => {
  decisionService.resetDemo();
  const cases = await decisionService.listCases();
  assert.deepEqual(new Set(cases.map(item => item.route)), new Set(['PRIORITY_REVIEW', 'HUMAN_REVIEW', 'OBSERVE', 'KNOWN_CANCELLATION', 'NOT_ELIGIBLE']));
  assert.equal(cases.find(item => item.customer_id === 'c01')?.owner, 'Janice');
  assert.equal(cases.find(item => item.customer_id === 'c03')?.owner, 'Jasmine');
  const quality = cases.find(item => item.customer_id === 'c07')!;
  assert.equal(proposalsFor(quality).find(item => item.id === 'DATA_INVESTIGATION')?.eligible, true);
  assert.equal(proposalsFor(quality).find(item => item.id === 'ACCOUNT_CHECK_IN')?.eligible, false);
});
test('decision checks role, reason, eligible action and appends audit', async () => {
  decisionService.resetDemo();
  const input = { kind: 'APPROVE' as const, action_id: 'ACCOUNT_CHECK_IN' as const, owner: 'Janice', reason: 'Review synthetic usage decline', due_at: '2026-10-12T12:00:00Z', actor: 'Demo Manager' };
  assert.throws(() => decisionService.recordDecision('demo_case_c02', input, 'Viewer'), /Manager role/);
  assert.throws(() => decisionService.recordDecision('demo_case_c02', { ...input, reason: '' }, 'Manager'), /Reason/);
  assert.throws(() => decisionService.recordDecision('demo_case_c02', { ...input, action_id: 'CONDITIONAL_DISCOUNT' }, 'Manager'), /eligible/);
  const before = getCapacity();
  const updated = decisionService.recordDecision('demo_case_c02', input, 'Manager');
  assert.equal(updated.status, 'ASSIGNED');
  assert.equal(updated.owner, 'Janice');
  assert.equal(updated.audit.at(-1)?.type, 'APPROVE');
  assert.equal(getCapacity().used_review_slots, before.used_review_slots + 1);
  assert.throws(() => decisionService.recordDecision('demo_case_c04', { ...input, action_id: 'DATA_INVESTIGATION', reason: 'Investigate stale billing' }, 'Manager'), /review slots/);
});
test('execution records actuals without claiming external action', async () => {
  decisionService.resetDemo();
  const updated = decisionService.recordExecution('demo_case_c01', { outcome: 'EXECUTED', reason: 'Demo task completed', actual_cost: { amount_minor: 14000, currency: 'MYR' }, actual_minutes: 17, follow_up_at: '2026-10-15T12:00:00Z', actor: 'Demo CSM' }, 'CSM');
  assert.equal(updated.status, 'EXECUTED');
  assert.equal(updated.actual_cost?.amount_minor, 14000);
  assert.equal(updated.audit.at(-1)?.type, 'EXECUTED');
  assert.throws(() => decisionService.recordExecution('demo_case_c01', { outcome: 'EXECUTED', reason: 'Again', actual_cost: null, actual_minutes: null, follow_up_at: null, actor: 'Demo CSM' }, 'CSM'), /Only assigned/);
});
test('follow-up is reasoned and append-only in the demo session', () => {
  decisionService.resetDemo();
  assert.throws(() => decisionService.recordFollowUp('demo_case_c03', '', 'Demo CSM', 'CSM'), /Reason/);
  const updated = decisionService.recordFollowUp('demo_case_c03', 'Outcome not yet known', 'Demo CSM', 'CSM');
  assert.equal(updated.status, 'FOLLOW_UP_COMPLETE');
  assert.equal(updated.audit.at(-1)?.type, 'FOLLOW_UP_COMPLETE');
});
