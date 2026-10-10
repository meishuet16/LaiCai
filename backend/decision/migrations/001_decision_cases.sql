-- 001_decision_cases.sql
-- Member 3 — Decision Engine
-- Creates the decision_cases table owned by Part 3.
--
-- Ref: RetainIQ_v2_Complete_Requirements.md §4.2, §7.2–7.7
--
-- Run with:
--   psql $DATABASE_URL -f backend/decision/migrations/001_decision_cases.sql

-- Enable uuid generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- decision_cases
-- One row per (tenant_id, customer_id, prediction_id) triple.
-- Links the prediction snapshot to the full review/action/outcome lifecycle.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_cases (
    case_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tenant isolation — every query MUST filter by tenant_id
    tenant_id           TEXT        NOT NULL,

    -- Account identity (paying subscription account, not individual seat)
    customer_id         TEXT        NOT NULL,

    -- FK to Member 2's predictions table
    prediction_id       TEXT        NOT NULL,
    prediction_run_id   TEXT,

    -- Point-in-time cutoff from the prediction
    as_of               TIMESTAMPTZ NOT NULL,

    -- Canonical route (§7.2)
    route               TEXT        NOT NULL
        CHECK (route IN (
            'PRIORITY_REVIEW',
            'HUMAN_REVIEW',
            'OBSERVE',
            'KNOWN_CANCELLATION',
            'NOT_ELIGIBLE'
        )),
    route_reason        TEXT        NOT NULL,

    -- Financial ranking inputs (null when MRR is missing — never 0)
    exposure_proxy_30d_minor    BIGINT,         -- p30 * mrr_minor, same currency
    as_of_mrr_minor             BIGINT,         -- from Member 1's account_mrr_as_of
    currency                    TEXT,           -- ISO-4217

    -- MRR quality
    mrr_completeness    TEXT
        CHECK (mrr_completeness IN ('complete', 'partial', 'missing')),
    mrr_basis_version   TEXT,

    -- Calibrated probabilities (copied from prediction for ranking queries)
    -- Part 3 MUST NOT rewrite these; they are Member 2's frozen outputs.
    p_churn_30d         NUMERIC(7, 6),   -- [0, 1]
    p_churn_7d          NUMERIC(7, 6),   -- urgency tie-break only
    p_churn_14d         NUMERIC(7, 6),

    -- Prediction quality signals
    reliability_status  TEXT        NOT NULL,
    data_freshness_status TEXT      NOT NULL,

    -- Policy version used to produce this routing decision
    policy_version      TEXT        NOT NULL DEFAULT 'routing_policy_v1',

    -- Cooldown flag at time of routing
    cooldown_active     BOOLEAN     NOT NULL DEFAULT FALSE,
    cooldown_expires_at TIMESTAMPTZ,

    -- Case lifecycle state (§7.7 state machine)
    case_status         TEXT        NOT NULL DEFAULT 'PROPOSED'
        CHECK (case_status IN (
            'PROPOSED',
            'HUMAN_REVIEWED',
            'ASSIGNED',
            'EXECUTED',
            'FOLLOW_UP_DUE',
            'CLOSED',
            'CLOSED_NO_ACTION',
            'REJECTED'
        )),

    -- Timestamps
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotency: one case per prediction per account per tenant
    UNIQUE (tenant_id, customer_id, prediction_id)
);

-- ---------------------------------------------------------------------------
-- Indexes for common query patterns
-- ---------------------------------------------------------------------------

-- List cases by tenant + route + status (main review queue query)
CREATE INDEX IF NOT EXISTS idx_dc_tenant_route_status
    ON decision_cases (tenant_id, route, case_status);

-- Financial ranking query: exposure DESC, p7 DESC, opened_at ASC
CREATE INDEX IF NOT EXISTS idx_dc_tenant_currency_ranking
    ON decision_cases (tenant_id, currency, exposure_proxy_30d_minor DESC NULLS LAST);

-- Lookup by prediction_id (Part 4 feedback joins)
CREATE INDEX IF NOT EXISTS idx_dc_prediction_id
    ON decision_cases (prediction_id);

-- Customer history lookup
CREATE INDEX IF NOT EXISTS idx_dc_tenant_customer
    ON decision_cases (tenant_id, customer_id);

-- ---------------------------------------------------------------------------
-- Row-Level Security — ensure tenant isolation at DB level
-- ---------------------------------------------------------------------------

ALTER TABLE decision_cases ENABLE ROW LEVEL SECURITY;

-- Drop policy if re-running migration
DROP POLICY IF EXISTS tenant_isolation ON decision_cases;

CREATE POLICY tenant_isolation ON decision_cases
    USING (tenant_id = current_setting('app.tenant_id', TRUE));

-- ---------------------------------------------------------------------------
-- auto-update updated_at on any row change
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_decision_cases_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dc_updated_at ON decision_cases;

CREATE TRIGGER trg_dc_updated_at
    BEFORE UPDATE ON decision_cases
    FOR EACH ROW
    EXECUTE FUNCTION update_decision_cases_updated_at();

-- ---------------------------------------------------------------------------
-- Verification query (run after migration to confirm)
-- ---------------------------------------------------------------------------
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'decision_cases'
-- ORDER BY ordinal_position;
