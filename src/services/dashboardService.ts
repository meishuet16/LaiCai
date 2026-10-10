import type { AccountRecord, DataMode } from '../domain/customer.ts';
import type { DecisionCase } from '../domain/decision.ts';
import type { IntegrationOverview } from '../domain/integration.ts';
import { decisionService } from './decisionService.ts';
import { fixtureIntegrationService } from './integrationService.ts';
import { fixtureDataSource, NotConnectedError } from './retainIQService.ts';

export type DashboardSnapshot = { accounts: AccountRecord[]; cases: DecisionCase[]; integration: IntegrationOverview; as_of: string | null; evidence_kind: 'demo_fixture' };
export interface DashboardDataSource { getSnapshot(mode: DataMode, signal?: AbortSignal): Promise<DashboardSnapshot> }
export const dashboardService: DashboardDataSource = {
  async getSnapshot(mode, signal) {
    if (mode !== 'demo_fixture') throw new NotConnectedError('Business Overview aggregates require connected customer, prediction, decision, and integration read APIs.');
    const [accounts, cases, integration] = await Promise.all([fixtureDataSource.listAccounts(signal), decisionService.listCases(signal), fixtureIntegrationService.getOverview(signal)]);
    return { accounts, cases, integration, as_of: null, evidence_kind: 'demo_fixture' };
  },
};
