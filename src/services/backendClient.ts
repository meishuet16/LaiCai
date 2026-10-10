import type { AccountRecord, Currency, Route } from '../domain/customer';
import type { Capacity, DecisionCase, DecisionInput, ExecutionInput } from '../domain/decision.ts';
import type { IntegrationOverview } from '../domain/integration.ts';
import { isBackendCurrency } from '../domain/currency.ts';

type BackendHealth = {
  status: 'ok';
  service: string;
  version: string;
  mode: 'database' | 'stateless_demo';
  data_mode: 'authenticated_backend' | 'frontend_fixture';
  data_tenant: string | null;
  data_as_of: string | null;
  evidence_kind: 'synthetic';
};

type DashboardAccountsResponse = {
  accounts: AccountRecord[];
  meta: {
    source: 'authenticated_backend_dataset';
    tenant_id: string;
    as_of: string;
    returned_accounts: number;
    total_accounts: number;
    predictions_available: boolean;
    prediction_count: number;
    decision_cases_available: boolean;
  };
};

type RouteResponse = {
  customer_id: string;
  prediction_id: string;
  route: Route;
  route_reason: string;
  exposure_proxy_30d_minor: number | null;
  currency: string | null;
};

const viteEnv = (import.meta as ImportMeta & { env?: ImportMetaEnv }).env;
const configuredBaseUrl = viteEnv?.VITE_API_BASE_URL?.trim().replace(/\/$/, '');
const apiBaseUrl = configuredBaseUrl || '/api';
const tenantId = viteEnv?.VITE_DEMO_TENANT_ID?.trim() || 'tenant_abc';

function apiUrl(path: string): string {
  return `${apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

async function requestJson<T>(path: string, init: RequestInit = {}, requestTenantId = tenantId): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  headers.set('X-Tenant-Id', requestTenantId);
  if (init.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(apiUrl(path), { ...init, headers });
  if (!response.ok) throw new Error(`Backend request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export function getBackendHealth(signal?: AbortSignal): Promise<BackendHealth> {
  return requestJson<BackendHealth>('/health', { signal });
}

export function getBackendDashboardAccounts(signal?: AbortSignal): Promise<DashboardAccountsResponse> {
  return requestJson<DashboardAccountsResponse>('/v1/dashboard/accounts', { signal });
}

function safeCurrency(value: string | null, fallback: Currency): Currency {
  return value && isBackendCurrency(value) ? value : fallback;
}

export type LearningOverview = {
  as_of: string;
  dataset_provenance: string;
  summary: {
    prospective_accounts: number; scored_accounts: number; abstained_accounts: number;
    coverage_rate: number | null; abstention_rate: number | null; monotonicity_rate: number | null;
    fresh_accounts: number; limited_evidence_accounts: number;
  };
  feedback: { horizon_days: number; feedback_state: 'PENDING' | 'INCOMPLETE' | 'INELIGIBLE' | 'MATURE'; count: number }[];
  releases: { model_version: string; release_role: string; governance_state: string; feature_version: string; calibration_version: string; label_policy_version: string; created_at: string; decision_reason: string }[];
  performance: { pr_auc: number | null; brier_score: number | null; recall_at_k: number | null; status: string };
};

export function getBackendIntegrations(signal?: AbortSignal): Promise<IntegrationOverview> {
  return requestJson<IntegrationOverview>('/v1/dashboard/integrations', { signal });
}

export function getBackendCases(signal?: AbortSignal): Promise<{ cases: DecisionCase[]; capacity: Capacity }> {
  return requestJson<{ cases: DecisionCase[]; capacity: Capacity }>('/v1/dashboard/cases', { signal });
}

export function getBackendLearning(signal?: AbortSignal): Promise<LearningOverview> {
  return requestJson<LearningOverview>('/v1/dashboard/learning', { signal });
}

export function postBackendDecision(caseId: string, input: DecisionInput, role: string): Promise<DecisionCase> {
  return requestJson<DecisionCase>(`/v1/dashboard/cases/${encodeURIComponent(caseId)}/decision`, { method: 'POST', body: JSON.stringify({ ...input, role }) });
}

export function postBackendExecution(caseId: string, input: ExecutionInput, role: string): Promise<DecisionCase> {
  return requestJson<DecisionCase>(`/v1/dashboard/cases/${encodeURIComponent(caseId)}/execution`, { method: 'POST', body: JSON.stringify({ ...input, role }) });
}

export function postBackendFollowUp(caseId: string, reason: string, actor: string, role: string): Promise<DecisionCase> {
  return requestJson<DecisionCase>(`/v1/dashboard/cases/${encodeURIComponent(caseId)}/follow-up`, { method: 'POST', body: JSON.stringify({ reason, actor, role }) });
}

export async function routeAccountThroughBackend(account: AccountRecord, signal?: AbortSignal): Promise<AccountRecord> {
  const prediction = account.prediction;
  if (!prediction || !prediction.tenant_id || !prediction.as_of) return account;
  const fallbackCurrency: Currency = account.mrr?.currency ?? 'MYR';
  const result = await requestJson<RouteResponse>('/v1/decisions/route', {
    method: 'POST',
    signal,
    body: JSON.stringify({
      ...prediction,
      mrr: {
        tenant_id: prediction.tenant_id,
        customer_id: prediction.customer_id,
        mrr_as_of: prediction.as_of,
        mrr_minor: account.mrr?.amount_minor ?? null,
        currency: fallbackCurrency,
        mrr_basis_version: 'mrr_policy_v1_2',
        subscription_count: account.mrr ? 1 : 0,
        mrr_completeness: account.mrr ? 'complete' : 'missing',
      },
      cooldown_active: false,
    }),
  }, prediction.tenant_id);
  const casePresentation: Record<Route, { status: string; next: string }> = {
    PRIORITY_REVIEW: { status: 'PROPOSED', next: 'Review account action' },
    HUMAN_REVIEW: { status: 'PROPOSED', next: 'Investigate evidence quality' },
    OBSERVE: { status: 'OBSERVE', next: 'Continue monitoring' },
    KNOWN_CANCELLATION: { status: 'KNOWN_CANCELLATION', next: 'Cancellation workflow' },
    NOT_ELIGIBLE: { status: 'NOT_ELIGIBLE', next: 'No retention action' },
  };
  const presentation = casePresentation[result.route];
  return {
    ...account,
    route: result.route,
    route_reason: result.route_reason,
    case_status: presentation.status,
    next_step: presentation.next,
    exposure_proxy: result.exposure_proxy_30d_minor == null
      ? null
      : { amount_minor: result.exposure_proxy_30d_minor, currency: safeCurrency(result.currency, fallbackCurrency) },
  };
}
