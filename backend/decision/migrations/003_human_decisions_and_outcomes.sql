-- 003_human_decisions_and_outcomes.sql
-- Member 3 — Decision Engine
-- Creates human_decisions, outcome_observations, and case_history audit tables.
--
-- Ref: RetainIQ_v2_Complete_Requirements.md §7.5, §7.7

-- ---------------------------------------------------------------------------
-- human_decisions
-- Append-only audit record of every human decision made on an action proposal.
-- Preserves original system proposal and final human choice.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS human_decisions (
    human_decision_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               TEXT        NOT NULL,
    case_id                 UUID        NOT NULL REFERENCES decision_cases(case_id) ON DELETE CASCADE,
    proposal_id             TEXT        NOT NULL,
    original_action_code    TEXT        NOT NULL,
    final_action_code       TEXT        NOT NULL,
    decision_type           TEXT        NOT NULL
        CHECK (decision_type IN ('APPROVE', 'MODIFY', 'REJECT', 'NO_INTERVENTION', 'DEFER')),
    reason                  TEXT        NOT NULL,
    actor                   TEXT        NOT NULL,
    assigned_owner          TEXT,
    monetary_cost_minor     BIGINT      NOT NULL DEFAULT 0,
    staff_minutes_spent     INT         NOT NULL DEFAULT 0,
    currency                TEXT        NOT NULL DEFAULT 'MYR',
    override_applied        BOOLEAN     NOT NULL DEFAULT FALSE,
    override_reason         TEXT,
    decided_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hd_tenant_case
    ON human_decisions (tenant_id, case_id);

CREATE INDEX IF NOT EXISTS idx_hd_tenant_decided_at
    ON human_decisions (tenant_id, decided_at DESC);

-- ---------------------------------------------------------------------------
-- outcome_observations
-- Operational follow-up records observed at 7, 14, and 30 days after anchor.
-- Unknown/incomplete observation is NOT a successful retention outcome (§7.7).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outcome_observations (
    observation_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               TEXT        NOT NULL,
    case_id                 UUID        NOT NULL REFERENCES decision_cases(case_id) ON DELETE CASCADE,
    follow_up_anchor        TIMESTAMPTZ NOT NULL,
    horizon_days            INT         NOT NULL CHECK (horizon_days IN (7, 14, 30)),
    observed_status         TEXT        NOT NULL
        CHECK (observed_status IN ('active', 'churned', 'pending_cancellation', 'downgraded', 'unknown')),
    observation_coverage    TEXT        NOT NULL
        CHECK (observation_coverage IN ('complete', 'partial', 'unknown')),
    source_ref              TEXT        NOT NULL,
    observed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oo_tenant_case_horizon
    ON outcome_observations (tenant_id, case_id, horizon_days);

-- ---------------------------------------------------------------------------
-- case_history
-- Immutable event ledger tracking case lifecycle transitions.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS case_history (
    event_id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               TEXT        NOT NULL,
    case_id                 UUID        NOT NULL REFERENCES decision_cases(case_id) ON DELETE CASCADE,
    event_type              TEXT        NOT NULL,
    actor                   TEXT        NOT NULL,
    details                 JSONB       NOT NULL DEFAULT '{}'::jsonb,
    occurred_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ch_tenant_case_time
    ON case_history (tenant_id, case_id, occurred_at ASC);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
ALTER TABLE human_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE outcome_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_hd ON human_decisions;
CREATE POLICY tenant_isolation_hd ON human_decisions
    AS RESTRICTIVE
    USING (tenant_id = CURRENT_SETTING('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_oo ON outcome_observations;
CREATE POLICY tenant_isolation_oo ON outcome_observations
    AS RESTRICTIVE
    USING (tenant_id = CURRENT_SETTING('app.current_tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_ch ON case_history;
CREATE POLICY tenant_isolation_ch ON case_history
    AS RESTRICTIVE
    USING (tenant_id = CURRENT_SETTING('app.current_tenant_id', true));
