-- 004_action_executions.sql
-- Member 3 — Decision Engine
-- Records ACTUAL execution events with real monetary and staff costs.
-- Distinct from human_decisions (predicted costs) per §7.7.
--
-- Ref: RetainIQ_v2_Complete_Requirements.md §7.7:
--   "Record predicted action cost and actual monetary/staff effort separately;
--    date of first response, completion/failure and source-backed customer follow-up."
--
-- Run with:
--   psql $DATABASE_URL -f backend/decision/migrations/004_action_executions.sql

-- ---------------------------------------------------------------------------
-- action_executions
-- Append-only record of execution outcomes.
-- State: EXECUTED | FAILED | CANCELLED
-- Predicted cost is on action_proposals; actual cost is here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS action_executions (
    execution_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               TEXT        NOT NULL,
    case_id                 UUID        NOT NULL REFERENCES decision_cases(case_id) ON DELETE CASCADE,
    proposal_id             TEXT        NOT NULL,  -- FK to action_proposals
    human_decision_id       TEXT        NOT NULL,  -- FK to human_decisions

    -- Execution outcome
    execution_status        TEXT        NOT NULL
        CHECK (execution_status IN ('EXECUTED', 'FAILED', 'CANCELLED')),
    execution_note          TEXT,                  -- reason for failure or cancellation

    -- ACTUAL costs — separate from predicted costs on action_proposals
    actual_monetary_cost_minor  BIGINT  NOT NULL DEFAULT 0,
    actual_staff_minutes        INT     NOT NULL DEFAULT 0,
    currency                    TEXT    NOT NULL DEFAULT 'MYR',

    -- Execution actors and timeline
    executed_by             TEXT        NOT NULL,
    first_response_at       TIMESTAMPTZ,  -- when action was first acted upon
    completed_at            TIMESTAMPTZ,  -- when case execution finished (or null if failed)
    follow_up_anchor        TIMESTAMPTZ,  -- start of 7/14/30d operational follow-up window

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ae_tenant_case
    ON action_executions (tenant_id, case_id);

CREATE INDEX IF NOT EXISTS idx_ae_tenant_execution_status
    ON action_executions (tenant_id, execution_status);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
ALTER TABLE action_executions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_ae ON action_executions;
CREATE POLICY tenant_isolation_ae ON action_executions
    AS RESTRICTIVE
    USING (tenant_id = CURRENT_SETTING('app.current_tenant_id', true));
