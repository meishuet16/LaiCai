import type { ActionId, ActionProposal, Capacity, DecisionCase, DecisionInput, ExecutionInput } from '../domain/decision';
import type { Money, Role } from '../domain/customer';

const cutoff = '2026-10-10T00:00:00Z';
const money = (amount_minor: number, currency: 'MYR' | 'SGD'): Money => ({ amount_minor, currency });
const auditTimes: Record<string, string> = { c01: '2026-10-08T08:00:00Z', c02: '2026-10-09T08:00:00Z', c03: '2026-10-05T08:00:00Z', c04: '2026-10-09T09:00:00Z', c05: '2026-10-09T08:00:00Z', c06: '2026-10-09T07:00:00Z', c07: '2026-10-09T09:30:00Z', c08: '2026-10-08T08:00:00Z', c09: '2026-10-09T08:00:00Z' };
const audit = (id: string, detail: string) => [{ id: `demo_audit_${id}_1`, at: auditTimes[id], actor: 'demo_policy_v1', type: 'ROUTED', detail }];
const seeds: DecisionCase[] = [
  { id: 'demo_case_c01', customer_id: 'c01', route: 'PRIORITY_REVIEW', route_reason: 'Verified failed-payment evidence', status: 'ASSIGNED', owner: 'Janice', created_at: '2026-10-08T08:00:00Z', due_at: '2026-10-11T12:00:00Z', fact_ids: ['billing_evt_101', 'billing_evt_102'], facts: ['Two synthetic failed-payment events in 30 days'], warnings: ['Payment recovery is a demo workflow; no payment system is connected.'], proposed_action: 'PAYMENT_RECOVERY', selected_action: 'PAYMENT_RECOVERY', estimated_cost: money(15000, 'MYR'), estimated_minutes: 15, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c01', 'Priority review; payment evidence verified in synthetic fixture.') },
  { id: 'demo_case_c02', customer_id: 'c02', route: 'PRIORITY_REVIEW', route_reason: 'Usage below personal baseline', status: 'PROPOSED', owner: null, created_at: '2026-10-09T08:00:00Z', due_at: '2026-10-12T12:00:00Z', fact_ids: ['usage_fact_201'], facts: ['Synthetic usage is 62% below the account baseline'], warnings: [], proposed_action: 'ACCOUNT_CHECK_IN', selected_action: null, estimated_cost: null, estimated_minutes: 0, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c02', 'Priority review; usage decline in synthetic fixture.') },
  { id: 'demo_case_c03', customer_id: 'c03', route: 'PRIORITY_REVIEW', route_reason: 'No recent sessions', status: 'FOLLOW_UP_DUE', owner: 'Jasmine', created_at: '2026-10-05T08:00:00Z', due_at: '2026-10-09T12:00:00Z', fact_ids: ['usage_fact_301'], facts: ['No synthetic session event for 11 days'], warnings: [], proposed_action: 'ACCOUNT_CHECK_IN', selected_action: 'ACCOUNT_CHECK_IN', estimated_cost: money(4000, 'MYR'), estimated_minutes: 20, actual_cost: money(3500, 'MYR'), actual_minutes: 18, response_at: '2026-10-06T10:00:00Z', completed_at: '2026-10-06T11:00:00Z', follow_up_at: '2026-10-09T12:00:00Z', audit: audit('c03', 'Priority review; account check-in recorded in synthetic fixture.') },
  { id: 'demo_case_c04', customer_id: 'c04', route: 'HUMAN_REVIEW', route_reason: 'Limited history and stale billing', status: 'PROPOSED', owner: null, created_at: '2026-10-09T09:00:00Z', due_at: '2026-10-11T12:00:00Z', fact_ids: ['quality_fact_401'], facts: ['Only nine days of synthetic history are available'], warnings: ['Billing freshness is partial; investigate before any customer action.'], proposed_action: 'DATA_INVESTIGATION', selected_action: null, estimated_cost: null, estimated_minutes: 0, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c04', 'Human review; billing freshness is insufficient.') },
  { id: 'demo_case_c08', customer_id: 'c08', route: 'PRIORITY_REVIEW', route_reason: 'Usage below personal baseline', status: 'HUMAN_REVIEWED', owner: null, created_at: '2026-10-08T08:00:00Z', due_at: '2026-10-12T12:00:00Z', fact_ids: ['usage_fact_801'], facts: ['Synthetic usage is 41% below the account baseline'], warnings: [], proposed_action: 'ACCOUNT_CHECK_IN', selected_action: null, estimated_cost: null, estimated_minutes: 0, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c08', 'Priority review; awaiting owner assignment.') },
  { id: 'demo_case_c06', customer_id: 'c06', route: 'KNOWN_CANCELLATION', route_reason: 'Cancellation known at cutoff', status: 'KNOWN_CANCELLATION', owner: null, created_at: '2026-10-09T07:00:00Z', due_at: null, fact_ids: ['subscription_evt_601'], facts: ['Synthetic cancellation request was available before cutoff'], warnings: ['Outside the risk-prioritization queue.'], proposed_action: null, selected_action: null, estimated_cost: null, estimated_minutes: 0, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c06', 'Known cancellation; standard workflow applies.') },
  { id: 'demo_case_c07', customer_id: 'c07', route: 'HUMAN_REVIEW', route_reason: 'Identity conflict and missing MRR', status: 'PROPOSED', owner: null, created_at: '2026-10-09T09:30:00Z', due_at: '2026-10-11T12:00:00Z', fact_ids: ['quality_fact_701'], facts: ['Synthetic identity mapping conflict'], warnings: ['MRR missing; no exposure or ROI estimate is valid.'], proposed_action: 'DATA_INVESTIGATION', selected_action: null, estimated_cost: null, estimated_minutes: 0, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c07', 'Human review; insufficient evidence for a score.') },
  { id: 'demo_case_c05', customer_id: 'c05', route: 'OBSERVE', route_reason: 'Below review priority', status: 'OBSERVE', owner: 'Janice', created_at: '2026-10-09T08:00:00Z', due_at: null, fact_ids: ['usage_fact_501'], facts: ['Synthetic recent usage remains near baseline'], warnings: [], proposed_action: null, selected_action: null, estimated_cost: null, estimated_minutes: 0, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c05', 'Observe only; no review slot or action proposed.') },
  { id: 'demo_case_c09', customer_id: 'c09', route: 'NOT_ELIGIBLE', route_reason: 'No active paid subscription', status: 'NOT_ELIGIBLE', owner: null, created_at: '2026-10-09T08:00:00Z', due_at: null, fact_ids: ['subscription_fact_901'], facts: ['Synthetic trial has no active paid subscription'], warnings: [], proposed_action: null, selected_action: null, estimated_cost: null, estimated_minutes: 0, actual_cost: null, actual_minutes: null, response_at: null, completed_at: null, follow_up_at: null, audit: audit('c09', 'Ineligible under demo eligibility policy.') },
];
let cases = structuredClone(seeds);
let sequence = 2;
const clone = <T,>(value: T): T => structuredClone(value);
const active = (item: DecisionCase) => ['HUMAN_REVIEWED', 'ASSIGNED', 'EXECUTED', 'FOLLOW_UP_DUE', 'FOLLOW_UP_COMPLETE'].includes(item.status);
const budget = [money(50000, 'MYR'), money(30000, 'SGD')];

export function proposalsFor(item: DecisionCase): ActionProposal[] {
  const currency = item.customer_id === 'c08' ? 'SGD' : 'MYR';
  const priority = item.route === 'PRIORITY_REVIEW';
  const investigation = item.route === 'HUMAN_REVIEW';
  return [
    { id: 'ACCOUNT_CHECK_IN', description: 'Assign a human account check-in; no outreach is sent by this demo.', availability: 'demo_operational', eligible: priority && item.customer_id !== 'c01', contraindication: priority ? (item.customer_id === 'c01' ? 'Verified payment issue has a more relevant proposal.' : null) : 'Only offered with sufficient, fresh usage evidence.', fact_ids: priority ? item.fact_ids : [], estimated_cost: money(4000, currency), estimated_minutes: 20, approval_role: 'Manager', cooldown: '30 days after an executed check-in' },
    { id: 'PAYMENT_RECOVERY', description: 'Assign a human payment-recovery task; no payment attempt is made.', availability: 'demo_operational', eligible: item.customer_id === 'c01', contraindication: item.customer_id === 'c01' ? null : 'Requires verified billing failure evidence.', fact_ids: item.customer_id === 'c01' ? item.fact_ids : [], estimated_cost: money(15000, currency), estimated_minutes: 15, approval_role: 'Manager', cooldown: '14 days after execution' },
    { id: 'DATA_INVESTIGATION', description: 'Investigate stale, missing, or conflicting source data before outreach.', availability: 'demo_operational', eligible: investigation, contraindication: investigation ? null : 'Reserved for data-quality review.', fact_ids: investigation ? item.fact_ids : [], estimated_cost: money(0, currency), estimated_minutes: 25, approval_role: 'Manager', cooldown: 'No automatic repeat while investigation remains open' },
    { id: 'NO_INTERVENTION', description: 'Record a reasoned no-action decision.', availability: 'simulation_only', eligible: priority || investigation, contraindication: priority || investigation ? null : 'No decision requested for this route.', fact_ids: item.fact_ids, estimated_cost: money(0, currency), estimated_minutes: 0, approval_role: 'Manager', cooldown: 'N/A' },
    { id: 'CONDITIONAL_DISCOUNT', description: 'Discount offer is not configured or approved.', availability: 'disabled', eligible: false, contraindication: 'No discount policy, approval, or fulfillment integration.', fact_ids: [], estimated_cost: null, estimated_minutes: 0, approval_role: 'Manager', cooldown: 'N/A' },
  ];
}

export function getCapacity(): Capacity {
  const activeCases = cases.filter(active);
  const used = budget.map(limit => money(cases.reduce((sum, item) => sum + (active(item) && item.estimated_cost?.currency === limit.currency ? item.estimated_cost.amount_minor : 0), 0), limit.currency));
  return { review_slots: 4, used_review_slots: activeCases.length, pending: cases.filter(item => ['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)).length, overdue: cases.filter(item => item.due_at && item.due_at < cutoff && !['REJECTED', 'CLOSED_NO_ACTION', 'CANCELLED'].includes(item.status)).length, staff_minutes_total: 120, staff_minutes_used: activeCases.reduce((sum, item) => sum + item.estimated_minutes, 0), budgets: clone(budget), budget_used: used, investigation_queue: cases.filter(item => item.route === 'HUMAN_REVIEW' && ['PROPOSED', 'DEFERRED'].includes(item.status)).length };
}

export const decisionService = {
  async listCases(signal?: AbortSignal): Promise<DecisionCase[]> { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return clone(cases); },
  async getCase(id: string, signal?: AbortSignal): Promise<DecisionCase | null> { if (signal?.aborted) throw new DOMException('Aborted', 'AbortError'); return clone(cases.find(item => item.id === id) ?? null); },
  async getCapacity(): Promise<Capacity> { return getCapacity(); },
  recordDecision(id: string, input: DecisionInput, role: Role): DecisionCase {
    if (role !== 'Manager') throw new Error('Demo Manager role is required for decisions.');
    const item = cases.find(value => value.id === id);
    if (!item || !['PROPOSED', 'HUMAN_REVIEWED', 'DEFERRED'].includes(item.status)) throw new Error('This case cannot accept a new decision.');
    if (!input.reason.trim() || !input.actor.trim()) throw new Error('Reason and actor are required.');
    const approving = input.kind === 'APPROVE' || input.kind === 'MODIFY';
    const action = proposalsFor(item).find(value => value.id === input.action_id);
    if (approving && (!action || !action.eligible || action.availability === 'disabled' || action.id === 'NO_INTERVENTION')) throw new Error('Select an eligible action proposal.');
    if (approving && !input.owner.trim()) throw new Error('An owner is required for assignment.');
    if (approving && action) {
      const capacity = getCapacity();
      const newSlot = !active(item);
      if (newSlot && capacity.used_review_slots >= capacity.review_slots) throw new Error('No demo review slots remain.');
      if (capacity.staff_minutes_used + action.estimated_minutes > capacity.staff_minutes_total) throw new Error('Demo staff-minute capacity would be exceeded.');
      const limit = capacity.budgets.find(value => value.currency === action.estimated_cost?.currency);
      const spent = capacity.budget_used.find(value => value.currency === action.estimated_cost?.currency);
      if (limit && spent && action.estimated_cost && spent.amount_minor + action.estimated_cost.amount_minor > limit.amount_minor) throw new Error('Demo discretionary budget would be exceeded.');
      item.status = 'ASSIGNED'; item.owner = input.owner.trim(); item.selected_action = action.id; item.estimated_cost = action.estimated_cost; item.estimated_minutes = action.estimated_minutes; item.due_at = input.due_at || item.due_at;
    } else if (input.kind === 'REJECT') item.status = 'REJECTED';
    else if (input.kind === 'NO_INTERVENTION') item.status = 'CLOSED_NO_ACTION';
    else if (input.kind === 'DEFER') { if (!input.due_at) throw new Error('A new due date is required to defer.'); item.status = 'DEFERRED'; item.due_at = input.due_at; }
    if (!approving) { item.selected_action = null; item.estimated_cost = null; item.estimated_minutes = 0; }
    item.audit.push({ id: `demo_audit_${item.customer_id}_${sequence++}`, at: new Date().toISOString(), actor: input.actor.trim(), type: input.kind, detail: `${input.reason.trim()}${approving ? ` · ${item.selected_action} · owner ${item.owner}` : ''}` });
    return clone(item);
  },
  recordExecution(id: string, input: ExecutionInput, role: Role): DecisionCase {
    if (!['Manager', 'CSM'].includes(role)) throw new Error('Demo Manager or CSM role is required for execution.');
    const item = cases.find(value => value.id === id);
    if (!item || item.status !== 'ASSIGNED') throw new Error('Only assigned cases can record execution.');
    if (!input.reason.trim() || !input.actor.trim()) throw new Error('Reason and actor are required.');
    if (input.actual_cost && (!Number.isFinite(input.actual_cost.amount_minor) || input.actual_cost.amount_minor < 0 || input.actual_cost.currency !== item.estimated_cost?.currency)) throw new Error('Actual cost must be non-negative and match the case currency.');
    if (input.actual_minutes != null && (!Number.isFinite(input.actual_minutes) || input.actual_minutes < 0)) throw new Error('Actual effort must be non-negative.');
    item.status = input.outcome; item.actual_cost = input.actual_cost; item.actual_minutes = input.actual_minutes; item.response_at = new Date().toISOString(); item.completed_at = item.response_at; item.follow_up_at = input.outcome === 'EXECUTED' ? input.follow_up_at : null;
    item.audit.push({ id: `demo_audit_${item.customer_id}_${sequence++}`, at: item.completed_at, actor: input.actor.trim(), type: input.outcome, detail: input.reason.trim() });
    return clone(item);
  },
  recordFollowUp(id: string, reason: string, actor: string, role: Role): DecisionCase {
    if (!['Manager', 'CSM'].includes(role)) throw new Error('Demo Manager or CSM role is required for follow-up.');
    const item = cases.find(value => value.id === id);
    if (!item || !['EXECUTED', 'FOLLOW_UP_DUE'].includes(item.status)) throw new Error('This case has no follow-up to record.');
    if (!reason.trim() || !actor.trim()) throw new Error('Reason and actor are required.');
    item.status = 'FOLLOW_UP_COMPLETE';
    item.audit.push({ id: `demo_audit_${item.customer_id}_${sequence++}`, at: new Date().toISOString(), actor: actor.trim(), type: 'FOLLOW_UP_COMPLETE', detail: reason.trim() });
    return clone(item);
  },
  resetDemo() { cases = clone(seeds); sequence = 2; },
};
