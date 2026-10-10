import type { AccountRecord, DataMode } from '../domain/customer.ts';
import type { DecisionCase } from '../domain/decision.ts';
import type { IntegrationOverview } from '../domain/integration.ts';
import { decisionDataSource } from './decisionService.ts';
import { integrationDataSource } from './integrationService.ts';
import { accountDataSource } from './retainIQService.ts';

export type DashboardSnapshot = { accounts: AccountRecord[]; cases: DecisionCase[]; integration: IntegrationOverview; as_of: string | null; evidence_kind: 'demo_fixture' | 'source_backed' };
export interface DashboardDataSource { getSnapshot(mode: DataMode, signal?: AbortSignal): Promise<DashboardSnapshot> }
export const dashboardService: DashboardDataSource = {
  async getSnapshot(mode, signal) {
    const [accounts, cases, integration] = await Promise.all([
      accountDataSource(mode).listAccounts(signal),
      decisionDataSource(mode).listCases(signal),
      integrationDataSource(mode).getOverview(signal),
    ]);
    const asOf = accounts.flatMap(account => account.prediction?.as_of ? [account.prediction.as_of] : []).sort().at(-1) ?? null;
    return { accounts, cases, integration, as_of: asOf, evidence_kind: mode === 'connected' ? 'source_backed' : 'demo_fixture' };
  },
};
