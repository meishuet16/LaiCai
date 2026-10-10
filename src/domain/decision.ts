import type { Money, Route } from './customer.ts';

export type CaseStatus = 'PROPOSED' | 'HUMAN_REVIEWED' | 'ASSIGNED' | 'EXECUTED' | 'FOLLOW_UP_DUE' | 'FOLLOW_UP_COMPLETE' | 'DEFERRED' | 'REJECTED' | 'CLOSED_NO_ACTION' | 'CANCELLED' | 'FAILED' | 'OBSERVE' | 'KNOWN_CANCELLATION' | 'NOT_ELIGIBLE';
export type ActionId = 'ACCOUNT_CHECK_IN' | 'PAYMENT_RECOVERY' | 'DATA_INVESTIGATION' | 'NO_INTERVENTION' | 'CONDITIONAL_DISCOUNT';
export type DecisionKind = 'APPROVE' | 'MODIFY' | 'REJECT' | 'NO_INTERVENTION' | 'DEFER';
export type ActionProposal = { id: ActionId; description: string; availability: 'demo_operational' | 'simulation_only' | 'disabled'; eligible: boolean; contraindication: string | null; fact_ids: string[]; estimated_cost: Money | null; estimated_minutes: number; approval_role: 'Manager'; cooldown: string };
export type AuditEntry = { id: string; at: string; actor: string; type: string; detail: string };
export type DecisionCase = { id: string; customer_id: string; route: Route; route_reason: string; status: CaseStatus; owner: string | null; created_at: string; due_at: string | null; fact_ids: string[]; facts: string[]; warnings: string[]; proposed_action: ActionId | null; selected_action: ActionId | null; estimated_cost: Money | null; estimated_minutes: number; actual_cost: Money | null; actual_minutes: number | null; response_at: string | null; completed_at: string | null; follow_up_at: string | null; audit: AuditEntry[] };
export type Capacity = { review_slots: number; used_review_slots: number; pending: number; overdue: number | null; staff_minutes_total: number; staff_minutes_used: number; budgets: Money[]; budget_used: Money[]; investigation_queue: number };
export type DecisionInput = { kind: DecisionKind; action_id: ActionId | null; reason: string; owner?: string; due_at: string | null; actor: string };
export type ExecutionInput = { outcome: 'EXECUTED' | 'CANCELLED' | 'FAILED'; reason: string; actual_cost: Money | null; actual_minutes: number | null; follow_up_at: string | null; actor: string };
