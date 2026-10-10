-- 002_action_proposals.sql
-- Member 3 — Decision Engine
-- Creates action_proposals and budget_config tables.
--
-- Ref: RetainIQ_v2_Complete_Requirements.md §7.4, §7.5
--
-- Run with:
--   psql $DATABASE_URL -f backend/decision/migrations/002_action_proposals.sql

-- ---------------------------------------------------------------------------
-- action_proposals
-- Stores fact-based candidate action proposals generated for decision cases.
-- Proposes eligible options, NOT proven causal interventions.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS action_proposals (
    proposal_id             TEXT        PRIMARY KEY,

    -- Tenant isolation
    tenant_id               TEXT        NOT NULL,

    -- Reference to the decision case
    case_id                 UUID        NOT NULL REFERENCES decision_cases(case_id) ON DELETE CASCADE,

    -- Account identity
    customer_id             TEXT        NOT NULL,

    -- Canonical action code (§7.4)
    action_code             TEXT        NOT NULL
        CHECK (action_code IN (
            'ACCOUNT_CHECK_IN',
            'PAYMENT_RECOVERY',
            'PRODUCT_WALKTHROUGH',
            'DATA_INVESTIGATION',
            'NO_INTERVENTION',
            'TECH_SUPPORT_ESCALATION',
            'PLAN_REVIEW',
            'PAUSE',
            'DOWNGRADE',
            'CONDITIONAL_DISCOUNT'
        )),

    catalogue_version       TEXT        NOT NULL DEFAULT 'action_catalog_v1',

    -- Mode: only operational / conditional can be approved live
    mode                    TEXT        NOT NULL DEFAULT 'operational'
        CHECK (mode IN ('operational', 'conditional', 'simulation_only', 'disabled')),

    -- Exact supporting source facts (e.g. usage_events, billing_events rows)
    supporting_fact_refs    JSONB       NOT NULL DEFAULT '[]'::jsonb,

    -- Machine-readable eligibility rationale
    eligibility_reason      TEXT        NOT NULL,

    -- Estimated costs and capacity requirements
    estimated_cost_minor    BIGINT      NOT NULL DEFAULT 0,
    currency                TEXT        NOT NULL DEFAULT 'MYR',
    estimated_staff_minutes INT         NOT NULL DEFAULT 0,
    cooldown_days           INT,
    approval_role           TEXT        NOT NULL DEFAULT 'retention_agent',

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes for action_proposals
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ap_tenant_case
    ON action_proposals (tenant_id, case_id);

CREATE INDEX IF NOT EXISTS idx_ap_tenant_customer
    ON action_proposals (tenant_id, customer_id);

CREATE INDEX IF NOT EXISTS idx_ap_tenant_action_code
    ON action_proposals (tenant_id, action_code);

-- ---------------------------------------------------------------------------
-- budget_config
-- Admin-configured capacity and budget caps (§7.5).
-- Configures K review slots, staff-minute caps, and monetary discretionary budget.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS budget_config (
    tenant_id               TEXT        NOT NULL,
    currency                TEXT        NOT NULL DEFAULT 'MYR',
    policy_period           TEXT        NOT NULL DEFAULT 'daily'
        CHECK (policy_period IN ('daily', 'weekly')),

    k_slots                 INT         NOT NULL DEFAULT 10 CHECK (k_slots > 0),
    staff_minutes_cap       INT         NOT NULL DEFAULT 480 CHECK (staff_minutes_cap >= 0),
    monetary_budget_minor   BIGINT      NOT NULL DEFAULT 100000 CHECK (monetary_budget_minor >= 0),

    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (tenant_id, currency, policy_period)
);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
ALTER TABLE action_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_ap ON action_proposals;
CREATE POLICY tenant_isolation_ap ON action_proposals
    AS RESTRICTIVE
    USING (tenant_id = CURRENT_SETTING('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_bc ON budget_config;
CREATE POLICY tenant_isolation_bc ON budget_config
    AS RESTRICTIVE
    USING (tenant_id = CURRENT_SETTING('app.current_tenant_id', true));
