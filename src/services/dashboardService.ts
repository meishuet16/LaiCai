import type { AccountRecord } from '../domain/customer';
import type { DecisionCase } from '../domain/decision';
import type { IntegrationOverview } from '../domain/integration';
import { decisionService } from './decisionService';
import { integrationService } from './integrationService';
import { retainIQService } from './retainIQService';

export type DashboardSnapshot = { accounts: AccountRecord[]; cases: DecisionCase[]; integration: IntegrationOverview; as_of: string; evidence_kind: 'synthetic' };
export interface DashboardDataSource { getSnapshot(signal?: AbortSignal): Promise<DashboardSnapshot> }
export const dashboardService: DashboardDataSource = {
  async getSnapshot(signal) {
    const [accounts, cases, integration] = await Promise.all([retainIQService.listAccounts(signal), decisionService.listCases(signal), integrationService.getOverview(signal)]);
    return { accounts, cases, integration, as_of: '2026-10-10T00:00:00Z', evidence_kind: 'synthetic' };
  },
};
